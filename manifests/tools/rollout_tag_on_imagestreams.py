#!/usr/bin/env -S uv run --project=../..
"""Roll workbench ImageStream tags forward from ``versions_config.yml``.

This updates only ImageStream YAML files under ``manifests/<variant>/base``.
Runtime ImageStreams are skipped. For ODH, the tool keeps exactly two tags
(``N`` and ``N-1``). For RHOAI, it prepends a new ``N`` tag and preserves the
existing history.
"""

from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parents[1]

_RECOMMENDED_KEY = "opendatahub.io/workbench-image-recommended"
_OUTDATED_KEY = "opendatahub.io/image-tag-outdated"
_COMMIT_KEY = "opendatahub.io/notebook-build-commit"
_PLACEHOLDER_RE = re.compile(r"^(?P<prefix>.+?)(?P<suffix>-(?:n|\d+(?:-\d+)*))_PLACEHOLDER$")


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


def rollout_variant(root: Path, variant: str, target_tag_name: str, *, dry_run: bool = False) -> list[Path]:
    base_dir = root / "manifests" / variant / "base"
    keep_history = variant == "rhoai"
    yml = YAML()
    yml.preserve_quotes = True
    yml.width = 1024 * 1024
    yml.explicit_start = True
    yml.indent(mapping=2, sequence=4, offset=2)
    changed_paths: list[Path] = []

    for path in sorted(
        path
        for path in base_dir.glob("*-imagestream.yaml")
        if not path.name.startswith("runtime-")
    ):
        if rollout_imagestream_file(path, target_tag_name, keep_history=keep_history, dry_run=dry_run, yml=yml):
            changed_paths.append(path)
    return changed_paths


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    config_path = args.config.resolve() if args.config is not None else root / "versions_config.yml"
    target_tag_name = load_release_tag(config_path)

    variants = ("odh", "rhoai") if args.target == "all" else (args.target,)
    changed_paths: list[Path] = []
    for variant in variants:
        changed_paths.extend(rollout_variant(root, variant, target_tag_name, dry_run=args.dry_run))

    if not changed_paths:
        print("ImageStream files already match the requested rollout.")
        return 0

    for path in changed_paths:
        print(f"Updated {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
