from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

INDEX_URL_PREFIX = "https://console.redhat.com/api/pypi/public-rhai/rhoai"
PUBLIC_PYPI_URL = "https://pypi.org/simple/"
RELEASE_TAG_RE = re.compile(
    r"^(?P<version>\d+\.\d+\.\d+)(?:-(?P<phase>[A-Za-z]+(?:\.\d+)?))?(?P<build>-\d+)?$"
)
ACCEL_SEGMENT_RE = re.compile(r"^(?P<kind>cuda|rocm)-(?P<version>[^-]+)(?P<suffix>-el.+)$")


@dataclass(frozen=True)
class RhdsReleaseInfo:
    full_version: str
    phase: str


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


def parse_rhds_release_from_base_image(base_image: str | None) -> RhdsReleaseInfo:
    if not base_image:
        raise ValueError("BASE_IMAGE is required for rhds profile")

    _name, separator, tag = base_image.rpartition(":")
    if not separator:
        raise ValueError(f"BASE_IMAGE is missing a tag: {base_image}")

    match = RELEASE_TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"BASE_IMAGE tag does not encode RHDS release info: {base_image}")

    phase = (match.group("phase") or "").replace(".", "")
    return RhdsReleaseInfo(full_version=match.group("version"), phase=phase)


def stream_token_from_base_image(base_image: str | None) -> str:
    if not base_image:
        raise ValueError("BASE_IMAGE is required for rhds profile")

    image_name = base_image.rpartition(":")[0]
    repo_name = image_name.rsplit("/", maxsplit=1)[-1]
    if repo_name == "cpu":
        return "cpu"

    match = ACCEL_SEGMENT_RE.fullmatch(repo_name)
    if not match:
        raise ValueError(f"BASE_IMAGE does not encode a supported RHDS stream: {base_image}")

    return f"{match.group('kind')}{match.group('version').removeprefix('v')}"


def build_rhds_index_url(release: RhdsReleaseInfo, stream_token: str, *, use_test: bool) -> str:
    release_segment = release_minor_version(release.full_version)
    phase_suffix = normalize_phase_for_index(release.phase)
    if phase_suffix:
        release_segment = f"{release_segment}-{phase_suffix}"
    stream_suffix = "-ubi9-test" if use_test else "-ubi9"
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


def resolve_effective_index_url(
    profile: str,
    base_image: str | None,
    *,
    probe_url_exists: Callable[[str], bool] = probe_url_exists,
) -> str:
    if profile == "odh":
        return PUBLIC_PYPI_URL
    if profile != "rhds":
        raise ValueError(f"Unsupported profile: {profile}")

    release = parse_rhds_release_from_base_image(base_image)
    stream_token = stream_token_from_base_image(base_image)
    production_url = build_rhds_index_url(release, stream_token, use_test=False)
    if probe_url_exists(production_url):
        return production_url
    return build_rhds_index_url(release, stream_token, use_test=True)
