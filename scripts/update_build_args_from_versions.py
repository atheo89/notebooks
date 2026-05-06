#!/usr/bin/env python3

"""Sync build-args/*.conf files from versions_config.yml."""

from __future__ import annotations

import argparse
import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT_DIR / "versions_config.yml"
RELEASE_SCHEMA = {
    "full_version": None,
    "rhds_os_base": None,
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
class RhdsReleaseInfo:
    full_version: str
    phase: str


@dataclass(frozen=True)
class VersionsConfig:
    release: ReleaseConfig
    base_image: dict[str, Any]

    def acc_version(self, accelerator: str, distribution: str, flavor: str | None = None) -> str:
        if accelerator == "cpu":
            raw = self.base_image[accelerator][distribution]["acc_version"]
        else:
            if flavor is None:
                raise ValueError(f"Flavor is required for accelerator '{accelerator}'")
            raw = self.base_image[accelerator][flavor][distribution]["acc_version"]
        return resolve_acc_version(raw, self.release)

@dataclass(frozen=True)
class ConfTarget:
    path: Path
    accelerator: str | None
    distribution: str | None
    flavor: str | None
    manage_base_image: bool


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


def parse_release_version(full_version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in full_version.split("."))
    except ValueError as exc:
        raise ValueError(f"Expected semantic version, got '{full_version}'") from exc


def normalize_rhds_phase_input(phase: str) -> str:
    normalized = phase.strip().lower()
    if normalized == "ga":
        return "ga"

    match = PHASE_WITH_NUMBER_RE.fullmatch(normalized)
    if match is None:
        raise ValueError(f"Unsupported RHDS phase override: {phase}")
    return f"{match.group('name')}.{match.group('number')}"


def parse_rhds_release_from_base_image(base_image: str) -> RhdsReleaseInfo:
    _name, separator, tag = base_image.rpartition(":")
    if not separator:
        raise ValueError(f"BASE_IMAGE is missing a tag: {base_image}")

    match = RELEASE_TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"BASE_IMAGE tag does not encode RHDS release info: {base_image}")

    phase = (match.group("phase") or "").replace(".", "")
    return RhdsReleaseInfo(full_version=match.group("version"), phase=phase)


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


def select_rhds_phase(tag: str, release: ReleaseConfig, rhds_phase_override: str | None = None) -> str | None:
    match = RELEASE_TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"BASE_IMAGE tag does not encode RHDS release info: {tag}")

    current_version = match.group("version")
    current_phase = match.group("phase")
    if parse_release_version(release.full_version) > parse_release_version(current_version):
        if rhds_phase_override is not None:
            selected_phase = normalize_rhds_phase_input(rhds_phase_override)
            return None if selected_phase == "ga" else selected_phase
        return "ea.1"
    return current_phase


def rewrite_rhds_tag(tag: str, release: ReleaseConfig, rhds_phase_override: str | None = None) -> str:
    match = RELEASE_TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"BASE_IMAGE tag does not encode RHDS release info: {tag}")

    phase = select_rhds_phase(tag, release, rhds_phase_override)
    build = match.group("build") or ""
    updated_tag = release.full_version
    if phase:
        updated_tag = f"{updated_tag}-{phase}"
    return f"{updated_tag}{build}"


def rewrite_base_image(
    base_image: str,
    acc_version: str,
    release: ReleaseConfig,
    *,
    distribution: str,
    rhds_phase_override: str | None = None,
) -> str:
    name, separator, tag = base_image.rpartition(":")
    if not separator:
        raise ValueError(f"BASE_IMAGE is missing a tag: {base_image}")

    updated_name = rewrite_image_name(name, acc_version, release)
    if distribution == "rhds":
        updated_tag = rewrite_rhds_tag(tag, release, rhds_phase_override)
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


def remove_conf_key(text: str, key: str) -> str:
    kept_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            kept_lines.append(line)
            continue
        existing_key, _, _value = stripped.partition("=")
        if existing_key.strip() == key:
            continue
        kept_lines.append(line)
    return "".join(kept_lines)


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
    return VersionsConfig(release=release, base_image=data["artifacts"]["base_image"])


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
                manage_base_image=True,
            )
        )
    return targets


def profile_for_distribution(distribution: str) -> str:
    if distribution == "rhds":
        return "rhds"
    if distribution == "odh":
        return "odh"
    raise ValueError(f"Unsupported profile distribution: {distribution}")


def plan_updates(
    root_dir: Path,
    config: VersionsConfig,
    *,
    rhds_phase_override: str | None = None,
) -> list[PlannedUpdate]:
    updates: list[PlannedUpdate] = []
    for target in collect_conf_targets(root_dir):
        original_text = target.path.read_text(encoding="utf-8")
        if target.distribution is None:
            raise ValueError(f"Target is missing distribution metadata: {target.path}")

        profile = profile_for_distribution(target.distribution)
        working_text = remove_conf_key(original_text, "INDEX_URL")
        working_text = ensure_conf_key(working_text, "PROFILE", profile, before_key="PYLOCK_FLAVOR")
        assignments = read_conf_assignments(working_text)
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
                rhds_phase_override=rhds_phase_override,
            )
            replacements["BASE_IMAGE"] = resolved_base_image

        updates.append(
            PlannedUpdate(
                target=target,
                original_text=original_text,
                updated_text=rewrite_conf_text(working_text, replacements),
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
    parser.add_argument(
        "--rhds-phase",
        help="Optional RHDS phase override for release-line bumps (for example: ea.1, ea2, ga)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if files need updates")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_versions_config(args.config)
    updates = plan_updates(args.root, config, rhds_phase_override=args.rhds_phase)
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
