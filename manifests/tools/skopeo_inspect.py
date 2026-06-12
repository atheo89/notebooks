"""Shared synchronous skopeo helpers."""

from __future__ import annotations

import json
import subprocess
from typing import Any


def _run_json(command: list[str], *, target: str, operation: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise ValueError(f"skopeo is required to run {operation}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"skopeo {operation} timed out for {target}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        raise ValueError(f"skopeo {operation} failed for {target}: {detail}")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"skopeo {operation} returned invalid JSON for {target}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"skopeo {operation} returned invalid JSON object for {target}")
    return payload


def list_repository_tags(
    repository: str,
    *,
    tag_cache: dict[str, tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    if tag_cache is not None and repository in tag_cache:
        return tag_cache[repository]

    payload = _run_json(
        ["skopeo", "list-tags", "--retry-times", "3", f"docker://{repository}"],
        target=repository,
        operation="list-tags",
    )
    tags = payload.get("Tags")
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError(f"skopeo list-tags returned invalid tags for {repository}")

    resolved_tags = tuple(tags)
    if tag_cache is not None:
        tag_cache[repository] = resolved_tags
    return resolved_tags


def inspect_digest(image_ref: str) -> str:
    payload = _run_json(
        [
            "skopeo",
            "inspect",
            "--retry-times",
            "3",
            "--override-arch",
            "amd64",
            "--override-os",
            "linux",
            f"docker://{image_ref}",
        ],
        target=image_ref,
        operation="inspect",
    )
    digest = payload.get("Digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise ValueError(f"skopeo inspect returned invalid digest for {image_ref}")
    return digest


def inspect_config(image_ref: str) -> dict[str, Any]:
    return _run_json(
        [
            "skopeo",
            "inspect",
            "--retry-times",
            "3",
            "--override-arch",
            "amd64",
            "--override-os",
            "linux",
            "--config",
            f"docker://{image_ref}",
        ],
        target=image_ref,
        operation="inspect --config",
    )
