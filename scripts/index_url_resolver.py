#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

import typer

RHOAI_INDEX_ROOT = "https://console.redhat.com/api/pypi/public-rhai/rhoai"
INDEX_CHECK_TIMEOUT_SECONDS = 5.0
SKOPEO_TIMEOUT_SECONDS = 60
SUPPORTED_BASE_IMAGE_PREFIX = "quay.io/aipcc/base-images/"


class IndexResolutionError(ValueError):
    """Raised when a build-args config cannot be resolved into an index URL."""


@dataclass(frozen=True)
class ResolvedIndexConfig:
    conf_file: Path
    product: str
    index_profile: str
    flavor: str
    base_image: str
    accelerator: str
    release: str
    index_url: str


_DESCRIPTION_INDEX_RE = re.compile(
    r"\bindex\s+(?P<release>[^/\s,]+)/(?P<accelerator>[a-z0-9.]+)-ubi9\b",
    flags=re.IGNORECASE,
)
_RELEASE_RE = re.compile(r"^(?P<minor>\d+\.\d+)(?:-(?P<ea>EA\d+))?$", flags=re.IGNORECASE)
_MAJOR_MINOR_VERSION_RE = re.compile(r"^(?P<major_minor>\d+\.\d+)(?:\.\d+)?(?:[-+].+)?$")

app = typer.Typer(add_completion=False, no_args_is_help=True)


def read_conf_file(conf_file: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in conf_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        entries[key.strip()] = value.strip()
    return entries


def is_konflux_conf(conf_file: Path) -> bool:
    return conf_file.name.startswith("konflux.")


def resolve_product(conf_file: Path, entries: dict[str, str]) -> str:
    product = entries.get("PRODUCT")
    if product:
        return product
    if is_konflux_conf(conf_file):
        return "rhoai"
    raise IndexResolutionError(f"PRODUCT is missing in {conf_file}")


def resolve_flavor(conf_file: Path, entries: dict[str, str]) -> str:
    if flavor := entries.get("PYLOCK_FLAVOR"):
        return flavor

    stem = conf_file.stem
    if stem.startswith("konflux."):
        return stem.removeprefix("konflux.")
    return stem


def normalize_release(release: str, conf_file: Path) -> str:
    match = _RELEASE_RE.fullmatch(release.strip())
    if match is None:
        raise IndexResolutionError(f"Unsupported index release in image metadata for {conf_file}: {release}")
    normalized_release = match.group("minor")
    ea = match.group("ea")
    return normalized_release if ea is None else f"{normalized_release}-EA{int(ea[2:])}"


def normalize_version(version: str, *, kind: str, conf_file: Path) -> str:
    match = _MAJOR_MINOR_VERSION_RE.fullmatch(version.strip())
    if match is None:
        raise IndexResolutionError(
            f"Unsupported {kind} version in image metadata for {conf_file}: {version}"
        )
    return match.group("major_minor")


def normalize_accelerator(accelerator: str, *, version: str | None, conf_file: Path) -> str:
    normalized = accelerator.strip().lower()
    if normalized == "cpu":
        return "cpu"
    if normalized == "cuda":
        if version is None:
            raise IndexResolutionError(f"CUDA version label is missing for {conf_file}")
        return f"cuda{normalize_version(version, kind='CUDA', conf_file=conf_file)}"
    if normalized == "rocm":
        if version is None:
            raise IndexResolutionError(f"ROCm version label is missing for {conf_file}")
        return f"rocm{normalize_version(version, kind='ROCm', conf_file=conf_file)}"
    if normalized.startswith("cuda"):
        return f"cuda{normalize_version(normalized.removeprefix('cuda'), kind='CUDA', conf_file=conf_file)}"
    if normalized.startswith("rocm"):
        return f"rocm{normalize_version(normalized.removeprefix('rocm'), kind='ROCm', conf_file=conf_file)}"
    raise IndexResolutionError(f"Unsupported accelerator label in image metadata for {conf_file}: {accelerator}")


def validate_base_image(base_image: str, conf_file: Path) -> None:
    if not base_image.startswith(SUPPORTED_BASE_IMAGE_PREFIX) or ":" not in base_image:
        raise IndexResolutionError(f"Unsupported BASE_IMAGE format in {conf_file}: {base_image}")


@cache
def _inspect_base_image_config(base_image: str) -> dict[str, object]:
    command = [
        "skopeo",
        "inspect",
        "--override-os=linux",
        "--override-arch=amd64",
        "--retry-times=5",
        "--config",
        f"docker://{base_image}",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=SKOPEO_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise IndexResolutionError(f"skopeo is required to inspect {base_image}") from exc
    except subprocess.TimeoutExpired as exc:
        raise IndexResolutionError(f"skopeo inspect timed out for {base_image}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "unknown error"
        raise IndexResolutionError(f"skopeo inspect failed for {base_image}: {stderr}") from exc

    try:
        loaded = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise IndexResolutionError(f"skopeo inspect returned invalid JSON for {base_image}") from exc

    if not isinstance(loaded, dict):
        raise IndexResolutionError(f"skopeo inspect returned an unsupported payload for {base_image}")
    return loaded


def extract_image_labels(image_config: dict[str, object], conf_file: Path) -> dict[str, str]:
    config_block = image_config.get("config")
    if isinstance(config_block, dict):
        labels = config_block.get("Labels")
        if isinstance(labels, dict):
            return {str(key): str(value) for key, value in labels.items()}

    labels = image_config.get("Labels")
    if isinstance(labels, dict):
        return {str(key): str(value) for key, value in labels.items()}

    raise IndexResolutionError(f"skopeo inspect did not expose image labels for {conf_file}")


def resolve_from_structured_labels(labels: dict[str, str], conf_file: Path) -> tuple[str, str] | None:
    release = labels.get("com.redhat.aiplatform.index_version")
    accelerator = labels.get("com.redhat.aiplatform.accelerator")
    if not release or not accelerator:
        return None

    version_label = None
    normalized_accelerator = accelerator.strip().lower()
    if normalized_accelerator == "cuda":
        version_label = labels.get("com.redhat.aiplatform.cuda_version")
    elif normalized_accelerator == "rocm":
        version_label = labels.get("com.redhat.aiplatform.rocm_version")

    return normalize_release(release, conf_file), normalize_accelerator(
        accelerator,
        version=version_label,
        conf_file=conf_file,
    )


def resolve_from_description_label(labels: dict[str, str], conf_file: Path) -> tuple[str, str] | None:
    for key in ("description", "io.k8s.description"):
        description = labels.get(key)
        if not description:
            continue
        match = _DESCRIPTION_INDEX_RE.search(description)
        if match is None:
            continue
        return normalize_release(match.group("release"), conf_file), normalize_accelerator(
            match.group("accelerator"),
            version=None,
            conf_file=conf_file,
        )
    return None


def resolve_release_and_accelerator(labels: dict[str, str], conf_file: Path) -> tuple[str, str]:
    if resolved := resolve_from_structured_labels(labels, conf_file):
        return resolved
    if resolved := resolve_from_description_label(labels, conf_file):
        return resolved
    raise IndexResolutionError(
        f"Image metadata for {conf_file} is missing supported index labels "
        "(expected com.redhat.aiplatform.* or a description label with 'index <release>/<accelerator>-ubi9')"
    )


def build_rhoai_index_url(*, release: str, accelerator: str) -> str:
    return f"{RHOAI_INDEX_ROOT}/{release}/{accelerator}-ubi9/simple/"


def build_rhoai_test_index_url(*, release: str, accelerator: str) -> str:
    return f"{RHOAI_INDEX_ROOT}/{release}/{accelerator}-ubi9-test/simple/"


def index_url_candidates(*, release: str, accelerator: str) -> tuple[str, str]:
    return (
        build_rhoai_index_url(release=release, accelerator=accelerator),
        build_rhoai_test_index_url(release=release, accelerator=accelerator),
    )


def ensure_json_format_param(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["format"] = ["json"]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def validated_index_probe_url(index_url: str) -> str:
    probe_url = ensure_json_format_param(index_url)
    parsed = urlparse(probe_url)
    expected_prefix = urlparse(RHOAI_INDEX_ROOT)
    if parsed.scheme != "https":
        raise IndexResolutionError(f"Unsupported index URL scheme for availability probe: {index_url}")
    if parsed.netloc != expected_prefix.netloc:
        raise IndexResolutionError(f"Unsupported index URL host for availability probe: {index_url}")
    if not parsed.path.startswith(expected_prefix.path):
        raise IndexResolutionError(f"Unsupported index URL path for availability probe: {index_url}")
    return probe_url


@cache
def index_url_exists(index_url: str) -> bool:
    request = Request(validated_index_probe_url(index_url), method="HEAD")  # noqa: S310
    try:
        with urlopen(request, timeout=INDEX_CHECK_TIMEOUT_SECONDS) as response:  # noqa: S310
            return 200 <= response.status < 400
    except HTTPError:
        return False
    except URLError:
        return False


def resolve_index_config(
    conf_file: Path,
    *,
    require_konflux: bool = False,
) -> ResolvedIndexConfig:
    if not conf_file.is_file():
        raise IndexResolutionError(f"Config file not found: {conf_file}")
    if require_konflux and not is_konflux_conf(conf_file):
        raise IndexResolutionError(f"RH index resolution currently supports only konflux.*.conf files: {conf_file}")

    entries = read_conf_file(conf_file)
    product = resolve_product(conf_file, entries)
    if product != "rhoai":
        raise IndexResolutionError(f"Unsupported PRODUCT for dynamic RH index resolution in {conf_file}: {product}")

    base_image = entries.get("BASE_IMAGE")
    if not base_image:
        raise IndexResolutionError(f"BASE_IMAGE is missing in {conf_file}")
    validate_base_image(base_image, conf_file)

    labels = extract_image_labels(_inspect_base_image_config(base_image), conf_file)
    release, accelerator = resolve_release_and_accelerator(labels, conf_file)
    flavor = resolve_flavor(conf_file, entries)
    production_url, test_url = index_url_candidates(release=release, accelerator=accelerator)

    if index_url_exists(production_url):
        selected_index_url = production_url
    elif index_url_exists(test_url):
        selected_index_url = test_url
    else:
        raise IndexResolutionError(
            f"Neither production nor -test RH index is available for {conf_file}: "
            f"{production_url} / {test_url}"
        )

    return ResolvedIndexConfig(
        conf_file=conf_file,
        product=product,
        index_profile="rhoai",
        flavor=flavor,
        base_image=base_image,
        accelerator=accelerator,
        release=release,
        index_url=selected_index_url,
    )


@app.command("index-url")
def print_index_url(
    conf_file: Annotated[str, typer.Argument(help="Path to build-args config file")],
) -> None:
    typer.echo(resolve_index_config(Path(conf_file)).index_url)


@app.callback()
def main() -> None:
    """Resolve dynamic index URLs from build-args config files."""


if __name__ == "__main__":
    app()
