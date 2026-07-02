from __future__ import annotations

import importlib
import io
import urllib.error

import pytest


def load_rollout():
    return importlib.import_module("manifests.tools.rollout_tag_on_imagestreams")


def test_select_latest_matching_odh_tag_ignores_early_access_tags() -> None:
    rollout = load_rollout()

    latest = rollout.select_latest_matching_odh_tag(
        ["3.4_ea1-v1.41", "3.4_ea2-v1.42", "3.4-v1.43"],
        "3.4",
    )

    assert latest == "3.4-v1.43"


def test_select_latest_matching_odh_tag_prefers_highest_ga_build() -> None:
    rollout = load_rollout()

    latest = rollout.select_latest_matching_odh_tag(
        ["3.3-v1.1", "3.4-v1.9", "3.4-v1.43", "3.4_ea2-v1.99"],
        "3.4",
    )

    assert latest == "3.4-v1.43"


def test_select_latest_matching_odh_tag_raises_when_only_early_access_tags_exist() -> None:
    rollout = load_rollout()

    with pytest.raises(ValueError, match="No published ODH GA tag found"):
        rollout.select_latest_matching_odh_tag(["3.4_ea1-v1.9", "3.4_ea2-v1.42"], "3.4")


def test_related_image_env_name_maps_py312_ubi9_workbench_keys() -> None:
    rollout = load_rollout()

    assert (
        rollout.related_image_env_name("odh-workbench-jupyter-minimal-cpu-py312-ubi9")
        == "RELATED_IMAGE_ODH_WORKBENCH_JUPYTER_MINIMAL_CPU_PY312_IMAGE"
    )
    assert rollout.related_image_env_name("odh-workbench-rstudio-minimal-cuda-py312-c9s") is None
    assert rollout.related_image_env_name("odh-workbench-jupyter-minimal-cpu-py311-ubi9") is None


def test_resolve_rhoai_build_config_source_falls_back_to_ea_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    rollout = load_rollout()
    requested_urls: list[str] = []

    class FakeResponse:
        def read(self) -> bytes:
            return b"spec: {}"

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_urlopen(url: str, timeout: int = 60) -> FakeResponse:
        url_str = str(url)
        requested_urls.append(url_str)
        if url_str.endswith("/rhoai-3.4/bundle/manifests/rhods-operator.clusterserviceversion.yaml"):
            raise urllib.error.HTTPError(url_str, 404, "Not Found", {}, io.BytesIO(b""))
        return FakeResponse()

    monkeypatch.setattr(rollout.urllib.request, "urlopen", fake_urlopen)

    branch, source_url = rollout.resolve_rhoai_build_config_source("3.4")

    assert branch == "rhoai-3.4-ea.2"
    assert source_url.endswith("/rhoai-3.4-ea.2/bundle/manifests/rhods-operator.clusterserviceversion.yaml")
    assert requested_urls[0].endswith("/rhoai-3.4/bundle/manifests/rhods-operator.clusterserviceversion.yaml")
    assert requested_urls[1].endswith("/rhoai-3.4-ea.2/bundle/manifests/rhods-operator.clusterserviceversion.yaml")
