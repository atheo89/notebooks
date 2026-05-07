#!/usr/bin/env python3
"""Refresh ``manifests/odh/base/commit-latest.env`` from ``vcs-ref`` image labels.

Reads ``params-latest.env``, inspects each image with ``skopeo``, writes 7-char git prefixes.
Run after changing ``params-latest.env`` (e.g. pinning workbench images to digests from ``params.env``).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import re
import sys
import typing

import structlog

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ci.logging_config import configure_logging
from manifests.tools.commit_env_refs import parse_env_file


log = structlog.get_logger()


async def get_image_vcs_ref(image_url: str, semaphore: asyncio.Semaphore) -> tuple[str, str | None]:
    """
    Asynchronously inspects a container image's configuration using skopeo
    and extracts the 'vcs-ref' label.

    Args:
        image_url: The full URL of the image to inspect
                   (e.g., 'quay.io/opendatahub/workbench-images@sha256:...').

    Returns:
        A tuple containing the original image_url and the value of the 'vcs-ref'
        label if found, otherwise None.
    """
    # Using 'docker://' prefix is required for skopeo to identify the transport.
    full_image_url = f"docker://{image_url}"

    # Use 'inspect --config' which is much faster as it only fetches the config blob.
    command = ["skopeo", "inspect", "--override-os=linux", "--override-arch=amd64", "--retry-times=5", "--config", full_image_url]

    log.info(f"Starting config inspection for: {image_url}")

    stdout, stderr, returncode = None, None, None
    try:
        async with semaphore:
            log.info(f"Semaphore acquired, starting skopeo inspect for: {image_url}")
            # Create an asynchronous subprocess
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            # Wait for the command to complete and capture output
            stdout, stderr = await process.communicate()
            returncode = process.returncode

        # Process the results outside the semaphore block
        if returncode != 0:
            log.error(f"Skopeo command failed for {image_url} with exit code {returncode}.")
            if stderr:
                log.error(f"Stderr: {stderr.decode().strip()}")
            return image_url, None

        if not stdout:
            log.error(f"Skopeo command returned success but stdout was empty for {image_url}.")
            return image_url, None

        # Decode and parse the JSON output from stdout
        # The output of 'inspect --config' is the image config JSON directly.
        image_config = json.loads(stdout.decode())

        # Safely extract the 'vcs-ref' label from the config's 'Labels'
        vcs_ref = image_config.get("config", {}).get("Labels", {}).get("vcs-ref")

        if vcs_ref:
            log.info(f"Successfully found 'vcs-ref' for {image_url}: {vcs_ref}")
        else:
            log.warning(f"'vcs-ref' label not found for {image_url}.")

        return image_url, vcs_ref

    except FileNotFoundError:
        log.error("The 'skopeo' command was not found. Please ensure it is installed and in your PATH.")
        return image_url, None
    except json.JSONDecodeError:
        # This error can now also happen if stdout is None or not valid JSON
        log.error(f"Failed to parse skopeo output as JSON for {image_url}.")
        if stdout:
            log.debug(f"Stdout from skopeo for {image_url}: {stdout.decode(errors='replace')}")
        return image_url, None
    except Exception as e:
        log.error("Unexpected error while processing image", image_url=image_url, exc_info=True)
        return image_url, None


async def inspect(images_to_inspect: typing.Iterable[str]) -> list[tuple[str, str | None]]:
    """
    Main function to orchestrate the concurrent inspection of multiple images.
    """
    semaphore = asyncio.Semaphore(22)  # Limit concurrent skopeo processes
    tasks = [get_image_vcs_ref(image, semaphore) for image in images_to_inspect]
    return await asyncio.gather(*tasks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-existing-on-failure",
        action="store_true",
        help="Preserve existing commit-latest.env values for image refs that cannot be inspected.",
    )
    return parser


def _load_params_latest_entries() -> list[tuple[str, str]]:
    with open(PROJECT_ROOT / "manifests/odh/base/params-latest.env", "rt") as file:
        return [
            tuple(line.strip().split("=", 1))
            for line in file.readlines()
            if line.strip() and not line.strip().startswith("#")
        ]


def merge_commit_latest_results(
    images_to_inspect: typing.Sequence[tuple[str, str]],
    results: typing.Sequence[tuple[str, str | None]],
    *,
    existing_commit_entries: dict[str, str],
    keep_existing_on_failure: bool = False,
) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    missing_keys: list[str] = []

    for image, result in zip(images_to_inspect, results, strict=True):
        variable, image_ref = image
        _inspected_image, commit_hash = result
        commit_key = re.sub(r"-n$", "-commit-n", variable)

        if commit_hash is not None:
            output.append((commit_key, commit_hash[:7]))
            continue

        if keep_existing_on_failure and commit_key in existing_commit_entries:
            preserved = existing_commit_entries[commit_key]
            log.warning(
                f"Keeping existing commit hash for unresolved image ref: {variable} -> {image_ref} ({preserved})"
            )
            output.append((commit_key, preserved[:7]))
            continue

        missing_keys.append(commit_key)

    if missing_keys:
        raise ValueError(
            "No refreshed or existing commit hash available for: "
            + ", ".join(sorted(missing_keys))
        )

    return sorted(output)


async def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    images_to_inspect = _load_params_latest_entries()
    results = await inspect(value for _, value in images_to_inspect)

    try:
        output = merge_commit_latest_results(
            images_to_inspect,
            results,
            existing_commit_entries=parse_env_file(PROJECT_ROOT / "manifests/odh/base/commit-latest.env"),
            keep_existing_on_failure=args.keep_existing_on_failure,
        )
    except ValueError as exc:
        log.error(f"Failed to get commit hash for some images: {exc}")
        return 1

    with open(PROJECT_ROOT / "manifests/odh/base/commit-latest.env", "wt") as file:
        for line in sorted(output):
            print(*line, file=file, sep="=", end="\n")
    return 0


if __name__ == '__main__':
    configure_logging()
    raise SystemExit(asyncio.run(main()))
