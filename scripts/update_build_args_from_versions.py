#!/usr/bin/env python3

"""Sync build-args/*.conf files from versions_config.yml."""

from __future__ import annotations

import argparse
import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT_DIR / "versions_config.yml"
INDEX_URL_PREFIX = "https://console.redhat.com/api/pypi/public-rhai/rhoai"
RELEASE_SCHEMA = {
    "full_version": None,
    "rhds_os_base": None,
}
PYTHON_INDEX_SCHEMA = {
    "rhds": None,
    "odh": None,
}
BASE_IMAGE_SCHEMA = {
    "cpu": {
        "rhds": {"acc_version": None},
        "odh": {"acc_version": None},
    },
    "cuda": {
        "minimal": {
            "rhds": {"acc_version": None},
            "odh": {"acc_version": None},
        },
        "pytorch": {
            "rhds": {"acc_version": None},
            "odh": {"acc_version": None},
        },
        "pytorch-llmcompressor": {
            "rhds": {"acc_version": None},
            "odh": {"acc_version": None},
        },
        "tensorflow": {
            "rhds": {"acc_version": None},
            "odh": {"acc_version": None},
        },
    },
    "rocm": {
        "minimal": {
            "rhds": {"acc_version": None},
            "odh": {"acc_version": None},
        },
        "pytorch": {
            "rhds": {"acc_version": None},
            "odh": {"acc_version": None},
        },
        "tensorflow": {
            "rhds": {"acc_version": None},
            "odh": {"acc_version": None},
        },
    },
}
ROOT_SCHEMA = {
    "schema_version": None,
    "release": RELEASE_SCHEMA,
    "python_index": PYTHON_INDEX_SCHEMA,
    "artifacts": {
        "base_image": BASE_IMAGE_SCHEMA,
    },
}
PHASE_WITH_NUMBER_RE = re.compile(r"^(?P<name>[A-Za-z]+)[.-]?(?P<number>\d+)$")
RELEASE_TAG_RE = re.compile(
    r"^(?P<version>\d+\.\d+\.\d+)(?:-(?P<phase>[A-Za-z]+(?:\.\d+)?))?(?P<build>-\d+)?$"
)
ACCEL_SEGMENT_RE = re.compile(r"^(?P<kind>cuda|rocm)-(?P<version>[^-]+)(?P<suffix>-el.+)$")


@dataclass(frozen=True)
class ReleaseConfig:
    full_version: str
    rhds_os_base: str


@dataclass(frozen=True)
class PythonIndexConfig:
    mode: str
    channel: str | None
    url: str | None


@dataclass(frozen=True)
class RhdsReleaseInfo:
    full_version: str
    phase: str


@dataclass(frozen=True)
class VersionsConfig:
    release: ReleaseConfig
    python_index: dict[str, PythonIndexConfig]
    base_image: dict[str, Any]

    def acc_version(self, accelerator: str, distribution: str, flavor: str | None = None) -> str:
        if accelerator == "cpu":
            raw = self.base_image[accelerator][distribution]["acc_version"]
        else:
            if flavor is None:
                raise ValueError(f"Flavor is required for accelerator '{accelerator}'")
            raw = self.base_image[accelerator][flavor][distribution]["acc_version"]
        return resolve_acc_version(raw, self.release)

    def index_config(self, distribution: str) -> PythonIndexConfig:
        return self.python_index[distribution]


@dataclass(frozen=True)
class ConfTarget:
    path: Path
    accelerator: str | None
    distribution: str | None
    flavor: str | None
    stream_token: str | None
    manage_base_image: bool
    manage_index_url: bool


@dataclass(frozen=True)
class PlannedUpdate:
    target: ConfTarget
    original_text: str
    updated_text: str


def scalar_to_string(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    raise TypeError(f"Unsupported scalar value: {value!r}")


def resolve_acc_version(value: object, release: ReleaseConfig) -> str:
    version = scalar_to_string(value)
    if version == "<full_version>":
        return release.full_version
    return version


def release_minor_version(full_version: str) -> str:
    parts = full_version.split(".")
    if len(parts) < 2:
        raise ValueError(f"Expected semantic version, got '{full_version}'")
    return ".".join(parts[:2])


def normalize_phase_for_index(phase: str) -> str:
    normalized = phase.strip().lower().replace(".", "")
    if not normalized or normalized == "ga":
        return ""
    return normalized.upper()


def parse_rhds_release_from_base_image(base_image: str) -> RhdsReleaseInfo:
    _name, separator, tag = base_image.rpartition(":")
    if not separator:
        raise ValueError(f"BASE_IMAGE is missing a tag: {base_image}")

    match = RELEASE_TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"BASE_IMAGE tag does not encode RHDS release info: {base_image}")

    phase = (match.group("phase") or "").replace(".", "")
    return RhdsReleaseInfo(full_version=match.group("version"), phase=phase)


def build_rh_index_url(release: RhdsReleaseInfo, stream_token: str, *, use_test_index: bool) -> str:
    release_segment = release_minor_version(release.full_version)
    phase_suffix = normalize_phase_for_index(release.phase)
    if phase_suffix:
        release_segment = f"{release_segment}-{phase_suffix}"
    stream_suffix = "-ubi9-test" if use_test_index else "-ubi9"
    return f"{INDEX_URL_PREFIX}/{release_segment}/{stream_token}{stream_suffix}/simple/"


def probe_url_exists(url: str) -> bool:
    request = Request(url, headers={"User-Agent": "notebooks-index-probe"})
    try:
        with urlopen(request, timeout=10) as response:
            return 200 <= getattr(response, "status", 200) < 300
    except HTTPError as exc:
        if exc.code == 404:
            return False
        raise ValueError(f"Failed to probe production RH index {url}: HTTP {exc.code}") from exc
    except URLError as exc:
        raise ValueError(f"Failed to probe production RH index {url}: {exc.reason}") from exc


def resolve_index_url(
    index_config: PythonIndexConfig,
    stream_token: str,
    *,
    base_image: str | None = None,
    probe_url_exists: Callable[[str], bool] = probe_url_exists,
) -> str:
    if index_config.mode == "rh-index":
        if base_image is None:
            raise ValueError("BASE_IMAGE is required for rh-index mode")
        release = parse_rhds_release_from_base_image(base_image)
        if index_config.channel == "test":
            return build_rh_index_url(release, stream_token, use_test_index=True)
        if index_config.channel == "production":
            return build_rh_index_url(release, stream_token, use_test_index=False)
        if index_config.channel == "auto":
            production_url = build_rh_index_url(release, stream_token, use_test_index=False)
            try:
                if probe_url_exists(production_url):
                    return production_url
            except ValueError:
                raise
            except OSError as exc:
                raise ValueError(f"Failed to probe production RH index {production_url}: {exc}") from exc
            return build_rh_index_url(release, stream_token, use_test_index=True)
        raise ValueError(f"Unsupported rh-index channel: {index_config.channel}")
    if index_config.mode == "public-index":
        if index_config.url is None:
            raise ValueError("python_index.<distribution>.url is required for public-index mode")
        return index_config.url
    raise ValueError(f"Unsupported python index mode: {index_config.mode}")


def normalize_stream_version(acc_version: str) -> str:
    return acc_version.removeprefix("v")


def rewrite_image_name(name: str, acc_version: str, release: ReleaseConfig) -> str:
    prefix, slash, repo_name = name.rpartition("/")
    if not slash:
        return name

    match = ACCEL_SEGMENT_RE.fullmatch(repo_name)
    if not match:
        return name

    normalized_version = normalize_stream_version(acc_version)
    updated_repo_name = f"{match.group('kind')}-{normalized_version}-{release.rhds_os_base}"
    return f"{prefix}{slash}{updated_repo_name}"


def rewrite_rhds_tag(tag: str, release: ReleaseConfig) -> str:
    match = RELEASE_TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"BASE_IMAGE tag does not encode RHDS release info: {tag}")

    phase = match.group("phase")
    build = match.group("build") or ""
    updated_tag = release.full_version
    if phase:
        updated_tag = f"{updated_tag}-{phase}"
    return f"{updated_tag}{build}"


def rewrite_base_image(base_image: str, acc_version: str, release: ReleaseConfig, *, distribution: str) -> str:
    name, separator, tag = base_image.rpartition(":")
    if not separator:
        raise ValueError(f"BASE_IMAGE is missing a tag: {base_image}")

    updated_name = rewrite_image_name(name, acc_version, release)
    if distribution == "rhds":
        updated_tag = rewrite_rhds_tag(tag, release)
    elif tag == "latest" or tag.startswith("v"):
        updated_tag = acc_version
    else:
        updated_tag = tag
    return f"{updated_name}:{updated_tag}"


def rewrite_conf_text(text: str, replacements: dict[str, str]) -> str:
    lines = text.splitlines(keepends=True)
    missing_keys = set(replacements)
    updated_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            updated_lines.append(line)
            continue

        key, _, _value = stripped.partition("=")
        key = key.strip()
        if key not in replacements:
            updated_lines.append(line)
            continue

        line_ending = "\n" if line.endswith("\n") else ""
        updated_lines.append(f"{key}={replacements[key]}{line_ending}")
        missing_keys.discard(key)

    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise ValueError(f"Missing expected keys: {missing}")

    return "".join(updated_lines)


def ensure_conf_key(text: str, key: str, value: str, *, before_key: str | None = None) -> str:
    assignments = read_conf_assignments(text)
    if key in assignments:
        return text

    lines = text.splitlines(keepends=True)
    insertion = f"{key}={value}\n"
    if before_key is not None:
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                continue
            existing_key, _, _existing_value = stripped.partition("=")
            if existing_key.strip() == before_key:
                return "".join([*lines[:idx], insertion, *lines[idx:]])
    line_ending = "" if not text or text.endswith("\n") else "\n"
    return f"{text}{line_ending}{insertion}"


def read_conf_assignments(text: str) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        assignments[key.strip()] = value.strip()
    return assignments


def validate_mapping_schema(data: object, expected: dict[str, Any], context: str) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at {context}")

    actual_keys = set(data)
    expected_keys = set(expected)
    unexpected_keys = sorted(actual_keys - expected_keys)
    missing_keys = sorted(expected_keys - actual_keys)

    if unexpected_keys:
        keys = ", ".join(unexpected_keys)
        raise ValueError(f"Unexpected keys under {context}: {keys}")
    if missing_keys:
        keys = ", ".join(missing_keys)
        raise ValueError(f"Missing keys under {context}: {keys}")

    for key, child_schema in expected.items():
        if isinstance(child_schema, dict):
            validate_mapping_schema(data[key], child_schema, f"{context}.{key}")


def parse_python_index_config(data: object, context: str) -> PythonIndexConfig:
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at {context}")

    actual_keys = set(data)
    allowed_keys = {"mode", "channel", "url"}
    unexpected_keys = sorted(actual_keys - allowed_keys)
    if unexpected_keys:
        keys = ", ".join(unexpected_keys)
        raise ValueError(f"Unexpected keys under {context}: {keys}")

    if "mode" not in data:
        raise ValueError(f"Missing keys under {context}: mode")

    mode = scalar_to_string(data["mode"])
    if mode == "rh-index":
        if "channel" not in data:
            raise ValueError(f"{context}.channel is required for rh-index mode")
        channel = scalar_to_string(data["channel"])
        if channel not in {"auto", "test", "production"}:
            raise ValueError(f"{context}.channel must be one of: auto, test, production")
        if "url" in data:
            raise ValueError(f"{context}.url is not supported for rh-index mode")
        return PythonIndexConfig(mode=mode, channel=channel, url=None)

    if mode == "public-index":
        if "url" not in data:
            raise ValueError(f"{context}.url is required for public-index mode")
        if "channel" in data:
            raise ValueError(f"{context}.channel is not supported for public-index mode")
        return PythonIndexConfig(mode=mode, channel=None, url=scalar_to_string(data["url"]))

    raise ValueError(f"Unsupported python index mode at {context}: {mode}")


def load_versions_config(path: Path) -> VersionsConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level mapping in {path}")

    validate_mapping_schema(data, ROOT_SCHEMA, "root")

    release_data = data["release"]
    release = ReleaseConfig(
        full_version=scalar_to_string(release_data["full_version"]),
        rhds_os_base=scalar_to_string(release_data["rhds_os_base"]),
    )
    python_index = {
        distribution: parse_python_index_config(index_data, f"python_index.{distribution}")
        for distribution, index_data in data["python_index"].items()
    }
    return VersionsConfig(release=release, python_index=python_index, base_image=data["artifacts"]["base_image"])


def classify_conf_name(name: str) -> tuple[str, str] | None:
    mapping = {
        "cpu.conf": ("cpu", "odh"),
        "cuda.conf": ("cuda", "odh"),
        "rocm.conf": ("rocm", "odh"),
        "konflux.cpu.conf": ("cpu", "rhds"),
        "konflux.cuda.conf": ("cuda", "rhds"),
        "konflux.rocm.conf": ("rocm", "rhds"),
    }
    return mapping.get(name)


def classify_flavor(relative_path: Path, accelerator: str) -> str | None:
    parts = relative_path.parts

    if accelerator == "cpu":
        if parts[0] in {"jupyter", "runtimes", "codeserver", "rstudio"}:
            return None
        raise ValueError(f"Unsupported CPU build-args path: {relative_path}")

    if accelerator == "cuda":
        if parts[:2] == ("jupyter", "minimal"):
            return "minimal"
        if parts[:2] in {("jupyter", "pytorch"), ("runtimes", "pytorch")}:
            return "pytorch"
        if parts[:2] in {("jupyter", "pytorch+llmcompressor"), ("runtimes", "pytorch+llmcompressor")}:
            return "pytorch-llmcompressor"
        if parts[:2] in {("jupyter", "tensorflow"), ("runtimes", "tensorflow")}:
            return "tensorflow"
        if parts[0] == "rstudio":
            # RStudio currently follows the CUDA tensorflow stream.
            return "tensorflow"
        raise ValueError(f"Unsupported CUDA build-args path: {relative_path}")

    if accelerator == "rocm":
        if parts[:2] == ("jupyter", "minimal"):
            return "minimal"
        if parts[:3] == ("jupyter", "rocm", "pytorch") or parts[:2] == ("runtimes", "rocm-pytorch"):
            return "pytorch"
        if parts[:3] == ("jupyter", "rocm", "tensorflow") or parts[:2] == ("runtimes", "rocm-tensorflow"):
            return "tensorflow"
        raise ValueError(f"Unsupported ROCm build-args path: {relative_path}")

    raise ValueError(f"Unsupported accelerator '{accelerator}'")


def collect_conf_targets(root_dir: Path) -> list[ConfTarget]:
    targets: list[ConfTarget] = []
    for path in sorted(root_dir.rglob("build-args/*.conf")):
        relative_path = path.relative_to(root_dir)

        if relative_path.parts[:2] == ("base-images", "build-args"):
            static_streams = {
                "cpu.conf": "cpu",
                "cuda12.9.conf": "cuda12.9",
                "cuda13.0.conf": "cuda13.0",
                "rocm7.1.conf": "rocm7.1",
            }
            stream_token = static_streams.get(path.name)
            if stream_token is None:
                continue
            targets.append(
                ConfTarget(
                    path=path,
                    accelerator=None,
                    distribution=None,
                    flavor=None,
                    stream_token=stream_token,
                    manage_base_image=False,
                    manage_index_url=True,
                )
            )
            continue

        classification = classify_conf_name(path.name)
        if classification is None:
            raise ValueError(f"Unsupported build-args filename: {relative_path}")

        accelerator, distribution = classification
        targets.append(
            ConfTarget(
                path=path,
                accelerator=accelerator,
                distribution=distribution,
                flavor=classify_flavor(relative_path, accelerator),
                stream_token=None,
                manage_base_image=True,
                manage_index_url=True,
            )
        )
    return targets


def stream_token_for_target(target: ConfTarget, config: VersionsConfig) -> str:
    if target.stream_token is not None:
        return target.stream_token
    if target.accelerator == "cpu":
        return "cpu"
    if target.accelerator is None or target.distribution is None:
        raise ValueError(f"Target is missing accelerator metadata: {target.path}")
    acc_version = config.acc_version(target.accelerator, target.distribution, target.flavor)
    return f"{target.accelerator}{normalize_stream_version(acc_version)}"


def index_distribution_for_target(target: ConfTarget) -> str:
    if target.distribution is not None:
        return target.distribution
    # base-images/build-args/*.conf are non-Konflux inputs, so they follow the ODH/public side.
    return "odh"


def profile_for_distribution(distribution: str) -> str:
    if distribution == "rhds":
        return "rhds"
    if distribution == "odh":
        return "odh"
    raise ValueError(f"Unsupported profile distribution: {distribution}")


def plan_updates(root_dir: Path, config: VersionsConfig) -> list[PlannedUpdate]:
    updates: list[PlannedUpdate] = []
    for target in collect_conf_targets(root_dir):
        original_text = target.path.read_text(encoding="utf-8")
        profile = profile_for_distribution(index_distribution_for_target(target))
        original_text = ensure_conf_key(original_text, "PROFILE", profile, before_key="PYLOCK_FLAVOR")
        assignments = read_conf_assignments(original_text)
        current_base_image = assignments.get("BASE_IMAGE")
        replacements: dict[str, str] = {}
        replacements["PROFILE"] = profile
        resolved_base_image = current_base_image

        if target.manage_base_image:
            if target.accelerator is None or target.distribution is None:
                raise ValueError(f"Target is missing base image metadata: {target.path}")
            if current_base_image is None:
                raise ValueError(f"Missing BASE_IMAGE in {target.path}")
            acc_version = config.acc_version(target.accelerator, target.distribution, target.flavor)
            resolved_base_image = rewrite_base_image(
                current_base_image,
                acc_version,
                config.release,
                distribution=target.distribution,
            )
            replacements["BASE_IMAGE"] = resolved_base_image

        if target.manage_index_url:
            replacements["INDEX_URL"] = resolve_index_url(
                config.index_config(index_distribution_for_target(target)),
                stream_token_for_target(target, config),
                base_image=resolved_base_image,
            )

        updates.append(
            PlannedUpdate(
                target=target,
                original_text=original_text,
                updated_text=rewrite_conf_text(original_text, replacements),
            )
        )
    return updates


def relative_display_path(root_dir: Path, path: Path) -> str:
    return path.relative_to(root_dir).as_posix()


def print_diff(root_dir: Path, update: PlannedUpdate) -> None:
    relative_path = relative_display_path(root_dir, update.target.path)
    diff = difflib.unified_diff(
        update.original_text.splitlines(),
        update.updated_text.splitlines(),
        fromfile=relative_path,
        tofile=relative_path,
        lineterm="",
    )
    print("\n".join(diff))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT_DIR, help="Repository root to scan")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to versions_config.yml")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if files need updates")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_versions_config(args.config)
    updates = plan_updates(args.root, config)
    changed_updates = [update for update in updates if update.original_text != update.updated_text]

    if args.dry_run or args.check:
        for update in changed_updates:
            print_diff(args.root, update)
        if changed_updates:
            print(f"{len(changed_updates)} build-args file(s) need updates.")
        else:
            print("Build-args files already match versions_config.yml.")
        return 1 if args.check and changed_updates else 0

    for update in changed_updates:
        update.target.path.write_text(update.updated_text, encoding="utf-8")
        print(f"Updated {relative_display_path(args.root, update.target.path)}")

    if not changed_updates:
        print("Build-args files already match versions_config.yml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
