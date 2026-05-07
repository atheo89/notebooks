#!/usr/bin/env -S uv run --project=../..
"""Prepare release tags for notebook manifest trees.

ODH is implemented first. The script rotates current ``-n`` image and commit
entries into a released suffix derived from the current N tag, rewrites ODH
workbench ImageStreams from ``N/N-1`` to ``new-N/old-N``, refreshes
``commit-latest.env``, and regenerates ``kustomization.yaml``.
"""

from __future__ import annotations

import argparse
import copy
import io
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from manifests.tools.commit_env_refs import parse_env_file  # noqa: E402

ManifestCallback = Callable[[], None]

_SEMVER_TAG_RE = re.compile(r"^\d+\.\d+$")
_LATEST_KEY_RE = re.compile(r"-n$")
_LATEST_PLACEHOLDER_RE = re.compile(r"-n_PLACEHOLDER$")
_ODH_WORKBENCH_KEY_PREFIX = "odh-workbench-"
_RELEASED_SUFFIX_RE = re.compile(r"(?P<suffix>-\d+-\d+)$")
_COMMIT_RELEASED_SUFFIX_RE = re.compile(r"-commit(?P<suffix>-\d+-\d+)$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["odh", "rhoai"], default="odh")
    parser.add_argument("--new-version", required=True, help="New top-level release tag name, e.g. 3.6")
    parser.add_argument("--dry-run", action="store_true", help="Show which files would change without writing")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if files need updates")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root")
    return parser


def released_suffix_for_tag(tag_name: str) -> str:
    if not _SEMVER_TAG_RE.fullmatch(tag_name):
        raise ValueError(f"Unsupported ODH release tag format: {tag_name}")
    return "-" + tag_name.replace(".", "-")


def rotate_env_mapping(latest_mapping: dict[str, str], *, released_suffix: str) -> dict[str, str]:
    rotated: dict[str, str] = {}
    for key, value in sorted(latest_mapping.items()):
        if _LATEST_KEY_RE.search(key) is None:
            raise ValueError(f"Latest env entry does not end with '-n': {key}")
        rotated[_LATEST_KEY_RE.sub(released_suffix, key)] = value
    return rotated


def odh_released_params_mapping(latest_mapping: dict[str, str], *, released_suffix: str) -> dict[str, str]:
    workbench_only = {key: value for key, value in latest_mapping.items() if key.startswith(_ODH_WORKBENCH_KEY_PREFIX)}
    return rotate_env_mapping(workbench_only, released_suffix=released_suffix)


def _existing_released_suffixes(env_mapping: dict[str, str]) -> set[str]:
    suffixes: set[str] = set()
    for key in env_mapping:
        match = _COMMIT_RELEASED_SUFFIX_RE.search(key) or _RELEASED_SUFFIX_RE.search(key)
        if match is not None:
            suffixes.add(match.group("suffix"))
    return suffixes


def _validate_odh_release_depth(base_dir: Path) -> None:
    suffixes = _existing_released_suffixes(parse_env_file(base_dir / "params.env"))
    suffixes.update(_existing_released_suffixes(parse_env_file(base_dir / "commit.env")))
    if len(suffixes) > 1:
        raise ValueError(f"ODH first pass only supports one released tag; found multiple released suffixes: {sorted(suffixes)}")


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def _dump_yaml(document: Any) -> str:
    stream = io.StringIO()
    _yaml().dump(document, stream)
    return stream.getvalue()


def _replace_latest_placeholder(value: str, released_suffix: str) -> str:
    if _LATEST_PLACEHOLDER_RE.search(value) is None:
        raise ValueError(f"Placeholder does not end with '-n_PLACEHOLDER': {value}")
    return _LATEST_PLACEHOLDER_RE.sub(f"{released_suffix}_PLACEHOLDER", value)


def _is_runtime_imagestream(document: Any) -> bool:
    labels = document.get("metadata", {}).get("labels", {})
    return labels.get("opendatahub.io/runtime-image") == "true"


def detect_current_odh_n_version(base_dir: Path) -> str:
    versions: set[str] = set()
    for path in sorted(base_dir.glob("*-imagestream.yaml")):
        document = _yaml().load(path.read_text())
        if _is_runtime_imagestream(document):
            continue
        tags = document.get("spec", {}).get("tags", [])
        if len(tags) != 2:
            raise ValueError(f"Expected exactly two tags in ODH workbench imagestream {path.name}")
        versions.add(str(tags[0]["name"]))
    if len(versions) != 1:
        raise ValueError(f"Expected one shared ODH current N version, found: {sorted(versions)}")
    return versions.pop()


def rotate_odh_workbench_tags(document: Any, *, new_version: str, released_suffix: str) -> bool:
    if _is_runtime_imagestream(document):
        return False

    tags = document.get("spec", {}).get("tags", [])
    if len(tags) != 2:
        raise ValueError(
            f"Expected exactly two tags in ODH workbench imagestream {document.get('metadata', {}).get('name')}"
        )

    old_latest = copy.deepcopy(tags[0])

    new_latest = copy.deepcopy(old_latest)
    new_latest["name"] = new_version

    new_released = copy.deepcopy(old_latest)
    new_released["name"] = str(old_latest["name"])
    new_released["from"]["name"] = _replace_latest_placeholder(new_released["from"]["name"], released_suffix)
    annotations = new_released.setdefault("annotations", {})
    annotations["opendatahub.io/notebook-build-commit"] = _replace_latest_placeholder(
        annotations["opendatahub.io/notebook-build-commit"],
        released_suffix,
    )
    if "opendatahub.io/workbench-image-recommended" in annotations:
        annotations["opendatahub.io/workbench-image-recommended"] = "false"
    annotations.pop("opendatahub.io/default-image", None)

    tags[0] = new_latest
    tags[1] = new_released
    return True


def _format_env(mapping: dict[str, str]) -> str:
    return "".join(f"{key}={value}\n" for key, value in sorted(mapping.items()))


def plan_odh_release_tags(base_dir: Path, *, new_version: str) -> dict[Path, str]:
    _validate_odh_release_depth(base_dir)
    current_version = detect_current_odh_n_version(base_dir)
    released_suffix = released_suffix_for_tag(current_version)

    planned: dict[Path, str] = {
        base_dir / "params.env": _format_env(
            odh_released_params_mapping(parse_env_file(base_dir / "params-latest.env"), released_suffix=released_suffix)
        ),
        base_dir / "commit.env": _format_env(
            rotate_env_mapping(parse_env_file(base_dir / "commit-latest.env"), released_suffix=released_suffix)
        ),
    }

    for path in sorted(base_dir.glob("*-imagestream.yaml")):
        document = _yaml().load(path.read_text())
        changed = rotate_odh_workbench_tags(document, new_version=new_version, released_suffix=released_suffix)
        if changed:
            planned[path] = _dump_yaml(document)

    return planned


def _apply_planned_files(planned: dict[Path, str]) -> None:
    for path, text in planned.items():
        path.write_text(text)


def _default_refresh_odh_commit_latest() -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "update-commit-latest-env.py"),
            "--keep-existing-on-failure",
        ],
        cwd=ROOT,
        check=True,
    )


def _default_generate_odh_kustomization() -> None:
    subprocess.run(
        [str(ROOT / "uv"), "run", "manifests/tools/generate_kustomization.py", "--target", "odh"],
        cwd=ROOT,
        check=True,
    )


def prepare_odh_release_tags(
    base_dir: Path,
    *,
    new_version: str,
    refresh_latest_commits: ManifestCallback | None = None,
    generate_kustomization: ManifestCallback | None = None,
) -> dict[Path, str]:
    planned = plan_odh_release_tags(base_dir, new_version=new_version)
    rollback_targets = set(planned)
    rollback_targets.add(base_dir / "commit-latest.env")
    rollback_targets.add(base_dir / "kustomization.yaml")
    original_contents = {path: path.read_text() for path in rollback_targets if path.exists()}

    _apply_planned_files(planned)
    try:
        (refresh_latest_commits or _default_refresh_odh_commit_latest)()
        (generate_kustomization or _default_generate_odh_kustomization)()
    except Exception:
        for path, text in original_contents.items():
            path.write_text(text)
        raise
    return planned


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.variant != "odh":
        raise SystemExit("Only --variant odh is implemented in this first pass")

    base_dir = args.root / "manifests" / "odh" / "base"
    planned = plan_odh_release_tags(base_dir, new_version=args.new_version)
    changed_paths = [path for path, text in planned.items() if path.read_text() != text]

    if args.check:
        if changed_paths:
            for path in changed_paths:
                print(path.relative_to(args.root))
            return 1
        return 0

    if args.dry_run:
        if changed_paths:
            for path in changed_paths:
                print(path.relative_to(args.root))
        else:
            print("No ODH release tag updates needed.")
        return 0

    if changed_paths:
        prepare_odh_release_tags(base_dir, new_version=args.new_version)
    else:
        print("No ODH release tag updates needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
