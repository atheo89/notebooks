from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_resolver_path = Path(__file__).resolve().parents[3] / "scripts" / "index_url_resolver.py"
_resolver_spec = importlib.util.spec_from_file_location("_index_url_resolver", _resolver_path)
if _resolver_spec is None or _resolver_spec.loader is None:
    raise RuntimeError(f"Failed to load resolver from {_resolver_path}")
resolver = importlib.util.module_from_spec(_resolver_spec)
sys.modules[_resolver_spec.name] = resolver
_resolver_spec.loader.exec_module(resolver)


def test_resolve_effective_index_url_returns_public_pypi_for_odh() -> None:
    assert resolver.resolve_effective_index_url("odh", None) == "https://pypi.org/simple/"


def test_resolve_effective_index_url_uses_rhds_production_when_available() -> None:
    assert resolver.resolve_effective_index_url(
        "rhds",
        "quay.io/aipcc/base-images/cuda-12.9-el9.6:3.5.0-ea.1-1777919771",
        probe_url_exists=lambda _url: True,
    ) == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA1/cuda12.9-ubi9/simple/"


def test_resolve_effective_index_url_falls_back_to_test_when_production_missing() -> None:
    assert resolver.resolve_effective_index_url(
        "rhds",
        "quay.io/aipcc/base-images/cpu:3.5.0-ea.1-1777920678",
        probe_url_exists=lambda _url: False,
    ) == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA1/cpu-ubi9-test/simple/"


def test_resolve_effective_index_url_requires_base_image_for_rhds() -> None:
    with pytest.raises(ValueError, match="BASE_IMAGE"):
        resolver.resolve_effective_index_url("rhds", None)
