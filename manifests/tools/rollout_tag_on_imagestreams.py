#!/usr/bin/env -S uv run --project=../..
"""Roll workbench ImageStream tags forward from ``versions_config.yml``.

This updates workbench ImageStream YAML files under ``manifests/<variant>/base``.
Runtime ImageStreams are skipped. For ODH, the tool also synchronizes released
``params.env`` / ``commit.env`` entries and regenerates ``kustomization.yaml``.
ODH keeps exactly two tags (``N`` and ``N-1``). RHOAI prepends a new ``N`` tag
and preserves existing history.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Iterator

from consolio import Consolio
import yaml
from manifests.tools.commit_env_refs import commit_field_key, parse_env_file
from manifests.tools.generate_kustomization import generate as generate_kustomization
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parents[1]

_RECOMMENDED_KEY = "opendatahub.io/workbench-image-recommended"
_OUTDATED_KEY = "opendatahub.io/image-tag-outdated"
_COMMIT_KEY = "opendatahub.io/notebook-build-commit"
_PLACEHOLDER_RE = re.compile(r"^(?P<prefix>.+?)(?P<suffix>-(?:n|\d+(?:-\d+)*))_PLACEHOLDER$")
_VERSIONED_KEY_RE = re.compile(r"^(?P<base>.+?)(?P<suffix>-(?:n|\d+(?:-\d+)*))$")
_ODH_RELEASE_FAMILY_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)$")
_ODH_GA_BUILD_TAG_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)-v\d+\.(?P<build>\d+)$")
_SKOPEO_INSPECT = importlib.import_module("manifests.tools.skopeo_inspect")


@dataclass(frozen=True)
class ReleasedOdhImage:
    base_key: str
    released_suffix: str
    released_param_key: str
    released_commit_key: str
    repository: str
    published_tag: str
    digest_ref: str
    commit_sha: str

    def progress_message(self) -> str:
        digest = self.digest_ref.rsplit("@", 1)[-1]
        return f"{self.base_key} commit={self.commit_sha} digest={digest}"


class StepReporter:
    def __init__(self, stream: Any | None = None) -> None:
        self.stream = sys.stdout if stream is None else stream
        self.is_tty = bool(getattr(self.stream, "isatty", lambda: False)())
        self.console = Consolio(
            spinner_type="dots",
            no_colors=not self.is_tty,
            no_animation=not self.is_tty,
        )

    def print_step(self, message: str) -> None:
        if not self.is_tty:
            print(message, file=self.stream, flush=True)
            return
        self.console.reset_indent()
        self.console.print("cmp", message)

    @contextmanager
    def running_step(
        self,
        start_message: str,
        done_message: str,
        *,
        animate: bool = False,
        total: int | None = None,
    ) -> Iterator[Callable[[str], None] | None]:
        if total is not None:
            self.print_step(start_message)
            completed = 0

            def track_item(message: str) -> None:
                nonlocal completed
                completed += 1
                detail = f"[{completed}/{total}] {message}"
                if self.is_tty:
                    self.console.print(1, "inf", detail)
                else:
                    print(f"  {detail}", file=self.stream, flush=True)
                self.stream.flush()

            try:
                yield track_item
            except Exception:
                raise
            else:
                self.print_step(done_message)
            return

        if not self.is_tty or not animate:
            self.print_step(start_message)
            try:
                yield None
            except Exception:
                raise
            else:
                self.print_step(done_message)
            return

        with self.console.spinner(start_message, inline=True):
            yield None
        self.console.print("cmp", done_message)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT_DIR,
        help="Repository root containing versions_config.yml and manifests/ (default: repo root)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to versions_config.yml (default: <root>/versions_config.yml)",
    )
    parser.add_argument(
        "--target",
        choices=("all", "odh", "rhoai"),
        default="all",
        help="Roll out only one manifests base directory (default: all)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Compute updates without writing files")
    return parser.parse_args(argv)


def load_release_tag(config_path: Path) -> str:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    full_version = data["release"]["full_version"]
    parts = full_version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected semantic release.full_version, got {full_version!r}")
    major, minor, _patch = parts
    return f"{int(major)}.{int(minor)}"


def build_yaml() -> YAML:
    yml = YAML()
    yml.preserve_quotes = True
    yml.width = 1024 * 1024
    yml.explicit_start = True
    yml.indent(mapping=2, sequence=4, offset=2)
    return yml


def iter_workbench_imagestream_paths(base_dir: Path) -> Iterator[Path]:
    yield from sorted(
        path
        for path in base_dir.glob("*-imagestream.yaml")
        if not path.name.startswith("runtime-")
    )


def update_tag_placeholders(tag: dict[str, Any], suffix: str) -> None:
    annotations = tag.setdefault("annotations", {})
    from_block = tag.setdefault("from", {})

    from_name = from_block.get("name")
    if not isinstance(from_name, str):
        raise ValueError(f"Missing DockerImage placeholder in tag: {tag!r}")
    match = _PLACEHOLDER_RE.match(from_name)
    if match is None:
        raise ValueError(f"Unsupported placeholder format: {from_name!r}")
    from_block["name"] = f"{match.group('prefix')}{suffix}_PLACEHOLDER"

    commit_value = annotations.get(_COMMIT_KEY)
    if commit_value is None:
        return
    if not isinstance(commit_value, str):
        raise ValueError(f"Unexpected commit placeholder type: {commit_value!r}")
    match = _PLACEHOLDER_RE.match(commit_value)
    if match is None:
        raise ValueError(f"Unsupported placeholder format: {commit_value!r}")
    annotations[_COMMIT_KEY] = f"{match.group('prefix')}{suffix}_PLACEHOLDER"


def _odh_ga_tag_sort_key(tag: str) -> tuple[int, str]:
    match = _ODH_GA_BUILD_TAG_RE.fullmatch(tag)
    if match is None:
        raise ValueError(f"Unsupported ODH GA build tag format: {tag!r}")
    return (int(match.group("build")), tag)


def select_latest_matching_odh_tag(tags: list[str], release_family: str) -> str:
    match = _ODH_RELEASE_FAMILY_RE.fullmatch(release_family)
    if match is None:
        raise ValueError(f"Unsupported ODH release family: {release_family!r}")
    target_major = int(match.group("major"))
    target_minor = int(match.group("minor"))

    matches: list[tuple[tuple[int, str], str]] = []
    for tag in tags:
        tag_match = _ODH_GA_BUILD_TAG_RE.fullmatch(tag)
        if tag_match is None:
            continue
        if int(tag_match.group("major")) != target_major or int(tag_match.group("minor")) != target_minor:
            continue
        matches.append((_odh_ga_tag_sort_key(tag), tag))

    if not matches:
        raise ValueError(
            f"No published ODH GA tag found for family '{release_family}' "
            "(expected format like '3.4-v1.43'; early-access tags are ignored)"
        )
    return max(matches, key=lambda item: item[0])[1]


def repository_from_image_ref(image_ref: str) -> str:
    repository = image_ref.split("@", 1)[0]
    last_colon = repository.rfind(":")
    last_slash = repository.rfind("/")
    if last_colon > last_slash:
        return repository[:last_colon]
    return repository


def extract_short_vcs_ref(config_payload: dict[str, Any], image_ref: str) -> str:
    labels = config_payload.get("config", {}).get("Labels")
    if not isinstance(labels, dict):
        labels = config_payload.get("Labels")
    if not isinstance(labels, dict):
        raise ValueError(f"skopeo inspect returned invalid labels for {image_ref}")
    vcs_ref = labels.get("vcs-ref")
    if not isinstance(vcs_ref, str) or len(vcs_ref) < 7:
        raise ValueError(f"skopeo inspect returned invalid vcs-ref for {image_ref}")
    return vcs_ref[:7]


def _list_repository_tags_cached(
    repository: str,
    tag_cache: dict[str, tuple[str, ...]],
    tag_cache_lock: Lock,
) -> tuple[str, ...]:
    with tag_cache_lock:
        cached = tag_cache.get(repository)
    if cached is not None:
        return cached

    resolved_tags = _SKOPEO_INSPECT.list_repository_tags(repository)
    with tag_cache_lock:
        tag_cache.setdefault(repository, resolved_tags)
        return tag_cache[repository]


def _resolve_odh_released_image(
    path: Path,
    params_latest: dict[str, str],
    *,
    tag_cache: dict[str, tuple[str, ...]],
    tag_cache_lock: Lock,
) -> ReleasedOdhImage:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    tags = data["spec"]["tags"]
    if len(tags) < 2:
        raise ValueError(f"{path.name} must have at least two tags to sync ODH env files")

    released_placeholder = tags[1]["from"]["name"]
    if not isinstance(released_placeholder, str):
        raise ValueError(f"{path.name} tag 1 missing from.name placeholder")
    match = _PLACEHOLDER_RE.match(released_placeholder)
    if match is None:
        raise ValueError(f"{path.name} tag 1 placeholder has unexpected format: {released_placeholder!r}")

    base_key = match.group("prefix")
    released_suffix = match.group("suffix")
    latest_key = f"{base_key}-n"
    latest_ref = params_latest.get(latest_key)
    if latest_ref is None:
        raise ValueError(f"Missing params-latest.env entry for {latest_key}")

    repository = repository_from_image_ref(latest_ref)
    repository_name = repository.rsplit("/", 1)[1]
    if repository_name != base_key:
        raise ValueError(
            f"params-latest.env value for {latest_key} does not match key base {base_key!r}: {latest_ref!r}"
        )

    release_family = str(tags[1]["name"])
    published_tags = list(_list_repository_tags_cached(repository, tag_cache, tag_cache_lock))
    published_tag = select_latest_matching_odh_tag(published_tags, release_family)
    inspected = _SKOPEO_INSPECT.inspect_image(f"{repository}:{published_tag}")
    digest_ref = f"{repository}@{inspected.digest}"
    commit_sha = extract_short_vcs_ref(inspected.payload, digest_ref)
    return ReleasedOdhImage(
        base_key=base_key,
        released_suffix=released_suffix,
        released_param_key=released_placeholder.removesuffix("_PLACEHOLDER"),
        released_commit_key=commit_field_key(base_key, released_suffix),
        repository=repository,
        published_tag=published_tag,
        digest_ref=digest_ref,
        commit_sha=commit_sha,
    )


def resolve_odh_released_images(
    base_dir: Path,
    *,
    paths: list[Path] | None = None,
    on_item: Callable[[str], None] | None = None,
) -> list[ReleasedOdhImage]:
    params_latest = parse_env_file(base_dir / "params-latest.env")
    imagestream_paths = list(paths if paths is not None else iter_workbench_imagestream_paths(base_dir))
    tag_cache: dict[str, tuple[str, ...]] = {}
    tag_cache_lock = Lock()
    released_images: list[ReleasedOdhImage | None] = [None] * len(imagestream_paths)
    worker_count = min(8, len(imagestream_paths) or 1)

    def resolve_at(index: int, path: Path) -> tuple[int, ReleasedOdhImage]:
        return index, _resolve_odh_released_image(
            path,
            params_latest,
            tag_cache=tag_cache,
            tag_cache_lock=tag_cache_lock,
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(resolve_at, index, path) for index, path in enumerate(imagestream_paths)
        ]
        for future in as_completed(futures):
            index, released_image = future.result()
            released_images[index] = released_image
            if on_item is not None:
                on_item(released_image.progress_message())

    return [image for image in released_images if image is not None]


def sync_managed_env_file(
    path: Path,
    desired_entries_by_base: dict[str, tuple[str, str]],
    *,
    managed_prefix: str,
    dry_run: bool = False,
) -> bool:
    current_entries = parse_env_file(path)
    updated_entries: list[tuple[str, str]] = []
    seen_bases: set[str] = set()

    for key, value in current_entries.items():
        match = _VERSIONED_KEY_RE.match(key)
        if match is None:
            updated_entries.append((key, value))
            continue

        base_key = match.group("base")
        if base_key in desired_entries_by_base:
            if base_key in seen_bases:
                continue
            updated_entries.append(desired_entries_by_base[base_key])
            seen_bases.add(base_key)
            continue

        if key.startswith(managed_prefix):
            continue
        updated_entries.append((key, value))

    for base_key, entry in desired_entries_by_base.items():
        if base_key not in seen_bases:
            updated_entries.append(entry)

    updated_text = "".join(f"{key}={value}\n" for key, value in updated_entries)
    current_text = path.read_text(encoding="utf-8")
    if updated_text == current_text:
        return False
    if not dry_run:
        path.write_text(updated_text, encoding="utf-8")
    return True


def sync_odh_params_env(base_dir: Path, released_images: list[ReleasedOdhImage], *, dry_run: bool = False) -> bool:
    desired_entries_by_base = {
        released_image.base_key: (released_image.released_param_key, released_image.digest_ref)
        for released_image in released_images
    }
    return sync_managed_env_file(
        base_dir / "params.env",
        desired_entries_by_base,
        managed_prefix="odh-workbench-",
        dry_run=dry_run,
    )


def sync_odh_commit_env(base_dir: Path, released_images: list[ReleasedOdhImage], *, dry_run: bool = False) -> bool:
    desired_entries_by_base = {
        f"{released_image.base_key}-commit": (released_image.released_commit_key, released_image.commit_sha)
        for released_image in released_images
    }
    return sync_managed_env_file(
        base_dir / "commit.env",
        desired_entries_by_base,
        managed_prefix="odh-workbench-",
        dry_run=dry_run,
    )


def regenerate_kustomization(base_dir: Path, *, dry_run: bool = False) -> bool:
    path = base_dir / "kustomization.yaml"
    generated_text = generate_kustomization(base_dir)
    current_text = path.read_text(encoding="utf-8")
    if generated_text == current_text:
        return False
    if not dry_run:
        path.write_text(generated_text, encoding="utf-8")
    return True


def normalize_rollout_state(tag: dict[str, Any], index: int) -> None:
    annotations = tag.setdefault("annotations", {})
    if index == 0:
        annotations[_RECOMMENDED_KEY] = SingleQuotedScalarString("true")
        annotations.pop(_OUTDATED_KEY, None)
        return
    if index == 1:
        annotations[_RECOMMENDED_KEY] = SingleQuotedScalarString("false")
        annotations.pop(_OUTDATED_KEY, None)
        return
    annotations.pop(_RECOMMENDED_KEY, None)
    annotations[_OUTDATED_KEY] = SingleQuotedScalarString("true")


def rollout_tag_sequence(tags: Any, target_tag_name: str, *, keep_history: bool) -> bool:
    if not tags:
        return False
    if str(tags[0].get("name")) == target_tag_name:
        return False

    historical_tags = [copy.deepcopy(tag) for tag in tags]
    new_latest = copy.deepcopy(tags[0])
    new_latest["name"] = DoubleQuotedScalarString(target_tag_name)

    rolled_tags = [new_latest, *historical_tags]
    for index, tag in enumerate(rolled_tags):
        suffix = "-n" if index == 0 else "-" + str(tag["name"]).replace(".", "-")
        update_tag_placeholders(tag, suffix)
        normalize_rollout_state(tag, index)

    if not keep_history:
        del rolled_tags[2:]

    tags.clear()
    tags.extend(rolled_tags)
    return True


def rollout_imagestream_file(path: Path, target_tag_name: str, *, keep_history: bool, dry_run: bool, yml: YAML) -> bool:
    with path.open("r", encoding="utf-8") as handle:
        docs = list(yml.load_all(handle))
    if not docs:
        return False

    document = docs[0]
    tags = document.get("spec", {}).get("tags")
    if tags is None:
        raise ValueError(f"ImageStream has no spec.tags: {path}")

    changed = rollout_tag_sequence(tags, target_tag_name, keep_history=keep_history)
    if changed and not dry_run:
        with path.open("w", encoding="utf-8") as handle:
            if len(docs) > 1:
                yml.dump_all(docs, handle)
            else:
                yml.dump(document, handle)
    return changed


def rollout_variant_imagestreams(root: Path, variant: str, target_tag_name: str, *, dry_run: bool = False) -> list[Path]:
    base_dir = root / "manifests" / variant / "base"
    keep_history = variant == "rhoai"
    yml = build_yaml()
    changed_paths: list[Path] = []

    for path in iter_workbench_imagestream_paths(base_dir):
        if rollout_imagestream_file(path, target_tag_name, keep_history=keep_history, dry_run=dry_run, yml=yml):
            changed_paths.append(path)
    return changed_paths


def run_odh_imagestream_rollout_step(
    root: Path,
    variants: tuple[str, ...],
    target_tag_name: str,
    *,
    dry_run: bool,
    reporter: StepReporter,
) -> list[Path]:
    with reporter.running_step(
        "1/3 Updating imagestreams with new tag",
        "1/3 Imagestreams updated",
    ):
        changed_paths: list[Path] = []
        for variant in variants:
            changed_paths.extend(rollout_variant_imagestreams(root, variant, target_tag_name, dry_run=dry_run))
        return changed_paths


def run_odh_params_step(
    base_dir: Path,
    *,
    dry_run: bool,
    reporter: StepReporter,
) -> tuple[list[Path], list[ReleasedOdhImage]]:
    changed_paths: list[Path] = []
    imagestream_paths = list(iter_workbench_imagestream_paths(base_dir))
    worker_count = min(8, len(imagestream_paths) or 1)
    with reporter.running_step(
        f"2/3 Updating the ODH params.env file ({len(imagestream_paths)} images, {worker_count} concurrent skopeo workers)",
        "2/3 ODH params.env file updated",
        total=len(imagestream_paths),
    ) as track_item:
        released_images = resolve_odh_released_images(
            base_dir,
            paths=imagestream_paths,
            on_item=track_item,
        )
        if sync_odh_params_env(base_dir, released_images, dry_run=dry_run):
            changed_paths.append(base_dir / "params.env")
    return changed_paths, released_images


def run_odh_commit_step(
    base_dir: Path,
    released_images: list[ReleasedOdhImage],
    *,
    dry_run: bool,
    reporter: StepReporter,
) -> list[Path]:
    changed_paths: list[Path] = []
    with reporter.running_step(
        "3/3 Updating the ODH commit.env and kustomization.yaml files",
        "3/3 ODH commit.env and kustomization.yaml updated",
    ):
        if sync_odh_commit_env(base_dir, released_images, dry_run=dry_run):
            changed_paths.append(base_dir / "commit.env")
        if regenerate_kustomization(base_dir, dry_run=dry_run):
            changed_paths.append(base_dir / "kustomization.yaml")
    return changed_paths


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    config_path = args.config.resolve() if args.config is not None else root / "versions_config.yml"
    target_tag_name = load_release_tag(config_path)
    variants = ("odh", "rhoai") if args.target == "all" else (args.target,)

    reporter = StepReporter()
    changed_paths: list[Path] = []

    if "odh" in variants:
        changed_paths.extend(
            run_odh_imagestream_rollout_step(
                root,
                variants,
                target_tag_name,
                dry_run=args.dry_run,
                reporter=reporter,
            )
        )
        if not args.dry_run:
            params_changed_paths, released_images = run_odh_params_step(
                root / "manifests" / "odh" / "base",
                dry_run=args.dry_run,
                reporter=reporter,
            )
            changed_paths.extend(params_changed_paths)
            changed_paths.extend(
                run_odh_commit_step(
                    root / "manifests" / "odh" / "base",
                    released_images,
                    dry_run=args.dry_run,
                    reporter=reporter,
                )
            )

    if "rhoai" in variants and "odh" not in variants:
        changed_paths.extend(rollout_variant_imagestreams(root, "rhoai", target_tag_name, dry_run=args.dry_run))

    if not changed_paths:
        if "odh" in variants and not args.dry_run:
            print("Rollout files already match the requested state.")
            return 0
        print("ImageStream files already match the requested rollout.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
