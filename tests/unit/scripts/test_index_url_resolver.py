from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import scripts.index_url_resolver as resolver


def write_conf(
    tmp_path: Path,
    name: str,
    lines: list[str],
) -> Path:
    conf_file = Path(tmp_path) / name
    conf_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return conf_file


def prod_index_url(*, release: str, accelerator: str) -> str:
    return f"https://console.redhat.com/api/pypi/public-rhai/rhoai/{release}/{accelerator}-ubi9/simple/"


def inspect_config(*, labels: dict[str, str]) -> dict[str, object]:
    return {"config": {"Labels": labels}}


def structured_labels(
    *,
    release: str,
    accelerator: str,
    version: str | None = None,
) -> dict[str, str]:
    labels = {
        "com.redhat.aiplatform.index_version": release,
        "com.redhat.aiplatform.accelerator": accelerator,
    }
    if accelerator == "cuda" and version is not None:
        labels["com.redhat.aiplatform.cuda_version"] = version
    if accelerator == "rocm" and version is not None:
        labels["com.redhat.aiplatform.rocm_version"] = version
    return labels


def test_index_url_candidates_use_prod_then_test_suffix() -> None:
    assert resolver.index_url_candidates(release="3.5-EA2", accelerator="cpu") == (
        "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/cpu-ubi9/simple/",
        "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/cpu-ubi9-test/simple/",
    )


def test_resolve_rhoai_cpu_index_from_konflux_conf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_file = write_conf(
        tmp_path,
        "konflux.cpu.conf",
        [
            "BASE_IMAGE=quay.io/aipcc/base-images/cpu:3.5.0-ea.2-1778762488",
            "PYLOCK_FLAVOR=cpu",
            "PRODUCT=rhoai",
        ],
    )
    monkeypatch.setattr(
        resolver,
        "index_url_exists",
        lambda url: url == prod_index_url(release="3.5-EA2", accelerator="cpu"),
    )
    monkeypatch.setattr(
        resolver,
        "_inspect_base_image_config",
        lambda base_image: inspect_config(labels=structured_labels(release="3.5-EA2", accelerator="cpu")),
    )

    resolved = resolver.resolve_index_config(conf_file)

    assert resolved.product == "rhoai"
    assert resolved.index_profile == "rhoai"
    assert resolved.flavor == "cpu"
    assert resolved.accelerator == "cpu"
    assert resolved.release == "3.5-EA2"
    assert resolved.index_url == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/cpu-ubi9/simple/"


def test_resolve_rhoai_cuda_index_from_konflux_conf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_file = write_conf(
        tmp_path,
        "konflux.cuda.conf",
        [
            "BASE_IMAGE=quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.2-1778760737",
            "PYLOCK_FLAVOR=cuda",
            "PRODUCT=rhoai",
        ],
    )
    monkeypatch.setattr(
        resolver,
        "index_url_exists",
        lambda url: url == prod_index_url(release="3.5-EA2", accelerator="cuda13.0"),
    )
    monkeypatch.setattr(
        resolver,
        "_inspect_base_image_config",
        lambda base_image: inspect_config(
            labels=structured_labels(release="3.5-EA2", accelerator="cuda", version="13.0.2")
        ),
    )

    resolved = resolver.resolve_index_config(conf_file)

    assert resolved.flavor == "cuda"
    assert resolved.accelerator == "cuda13.0"
    assert resolved.release == "3.5-EA2"
    assert resolved.index_url == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/cuda13.0-ubi9/simple/"


def test_resolve_rhoai_rocm_index_from_konflux_conf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_file = write_conf(
        tmp_path,
        "konflux.rocm.conf",
        [
            "BASE_IMAGE=quay.io/aipcc/base-images/rocm-7.1-el9.6:3.5.0-ea.2-1778760581",
            "PYLOCK_FLAVOR=rocm",
            "PRODUCT=rhoai",
        ],
    )
    monkeypatch.setattr(
        resolver,
        "index_url_exists",
        lambda url: url == prod_index_url(release="3.5-EA2", accelerator="rocm7.1"),
    )
    monkeypatch.setattr(
        resolver,
        "_inspect_base_image_config",
        lambda base_image: inspect_config(
            labels=structured_labels(release="3.5-EA2", accelerator="rocm", version="7.1.0")
        ),
    )

    resolved = resolver.resolve_index_config(conf_file)

    assert resolved.flavor == "rocm"
    assert resolved.accelerator == "rocm7.1"
    assert resolved.release == "3.5-EA2"
    assert resolved.index_url == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/rocm7.1-ubi9/simple/"


def test_reject_non_konflux_conf_when_required(tmp_path: Path) -> None:
    conf_file = write_conf(
        tmp_path,
        "cpu.conf",
        [
            "BASE_IMAGE=quay.io/opendatahub/odh-base-image-cpu-py312-c9s:latest",
            "PYLOCK_FLAVOR=cpu",
            "PRODUCT=odh",
        ],
    )

    with pytest.raises(resolver.IndexResolutionError, match="konflux"):
        resolver.resolve_index_config(conf_file, require_konflux=True)


def test_resolve_rhoai_falls_back_to_test_index_when_prod_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_file = write_conf(
        tmp_path,
        "konflux.cpu.conf",
        [
            "BASE_IMAGE=quay.io/aipcc/base-images/cpu:3.5.0-ea.2-1778762488",
            "PYLOCK_FLAVOR=cpu",
            "PRODUCT=rhoai",
        ],
    )

    checked_urls: list[str] = []

    def fake_index_url_exists(url: str) -> bool:
        checked_urls.append(url)
        return url.endswith("/cpu-ubi9-test/simple/")

    monkeypatch.setattr(resolver, "index_url_exists", fake_index_url_exists)
    monkeypatch.setattr(
        resolver,
        "_inspect_base_image_config",
        lambda base_image: inspect_config(labels=structured_labels(release="3.5-EA2", accelerator="cpu")),
    )

    resolved = resolver.resolve_index_config(conf_file)

    assert resolved.index_url == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/cpu-ubi9-test/simple/"
    assert checked_urls == [
        "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/cpu-ubi9/simple/",
        "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/cpu-ubi9-test/simple/",
    ]


def test_resolve_rhoai_does_not_check_test_when_prod_is_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_file = write_conf(
        tmp_path,
        "konflux.cpu.conf",
        [
            "BASE_IMAGE=quay.io/aipcc/base-images/cpu:3.5.0-ea.2-1778762488",
            "PYLOCK_FLAVOR=cpu",
            "PRODUCT=rhoai",
        ],
    )

    checked_urls: list[str] = []

    def fake_index_url_exists(url: str) -> bool:
        checked_urls.append(url)
        return url.endswith("/cpu-ubi9/simple/")

    monkeypatch.setattr(resolver, "index_url_exists", fake_index_url_exists)
    monkeypatch.setattr(
        resolver,
        "_inspect_base_image_config",
        lambda base_image: inspect_config(labels=structured_labels(release="3.5-EA2", accelerator="cpu")),
    )

    resolved = resolver.resolve_index_config(conf_file)

    assert resolved.index_url == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/cpu-ubi9/simple/"
    assert checked_urls == [
        "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/cpu-ubi9/simple/",
    ]


def test_cli_prints_plain_index_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_file = write_conf(
        tmp_path,
        "konflux.rocm.conf",
        [
            "BASE_IMAGE=quay.io/aipcc/base-images/rocm-7.1-el9.6:3.5.0-ea.2-1778760581",
            "PYLOCK_FLAVOR=rocm",
            "PRODUCT=rhoai",
        ],
    )
    monkeypatch.setattr(
        resolver,
        "index_url_exists",
        lambda url: url == prod_index_url(release="3.5-EA2", accelerator="rocm7.1"),
    )
    monkeypatch.setattr(
        resolver,
        "_inspect_base_image_config",
        lambda base_image: inspect_config(
            labels=structured_labels(release="3.5-EA2", accelerator="rocm", version="7.1.0")
        ),
    )

    runner = CliRunner()
    result = runner.invoke(resolver.app, ["index-url", str(conf_file)])

    assert result.exit_code == 0
    assert result.stdout.strip() == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/rocm7.1-ubi9/simple/"


def test_resolve_rhoai_cuda_index_from_structured_skopeo_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_file = write_conf(
        tmp_path,
        "konflux.cuda.conf",
        [
            "BASE_IMAGE=quay.io/aipcc/base-images/cuda-stable-ubi9:3.5",
            "PYLOCK_FLAVOR=cuda",
            "PRODUCT=rhoai",
        ],
    )
    monkeypatch.setattr(
        resolver,
        "_inspect_base_image_config",
        lambda base_image: inspect_config(
            labels={
                "com.redhat.aiplatform.index_version": "3.5",
                "com.redhat.aiplatform.accelerator": "cuda",
                "com.redhat.aiplatform.cuda_version": "13.0.2",
            }
        ),
        raising=False,
    )
    monkeypatch.setattr(
        resolver,
        "index_url_exists",
        lambda url: url == prod_index_url(release="3.5", accelerator="cuda13.0"),
    )

    resolved = resolver.resolve_index_config(conf_file)

    assert resolved.accelerator == "cuda13.0"
    assert resolved.release == "3.5"
    assert resolved.index_url == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5/cuda13.0-ubi9/simple/"


def test_resolve_rhoai_falls_back_to_description_label(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_file = write_conf(
        tmp_path,
        "konflux.rocm.conf",
        [
            "BASE_IMAGE=quay.io/aipcc/base-images/rocm-stable-ubi9:3.5",
            "PYLOCK_FLAVOR=rocm",
            "PRODUCT=rhoai",
        ],
    )
    monkeypatch.setattr(
        resolver,
        "_inspect_base_image_config",
        lambda base_image: inspect_config(
            labels={
                "description": (
                    "Red Hat AI Base Image for AMD ROCm 7.1 on RHEL 9.6 "
                    "with index 3.5-EA2/rocm7.1-ubi9, Python 3.12, and AI repo 3.5"
                )
            }
        ),
        raising=False,
    )
    monkeypatch.setattr(
        resolver,
        "index_url_exists",
        lambda url: url == prod_index_url(release="3.5-EA2", accelerator="rocm7.1"),
    )

    resolved = resolver.resolve_index_config(conf_file)

    assert resolved.accelerator == "rocm7.1"
    assert resolved.release == "3.5-EA2"
    assert resolved.index_url == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/rocm7.1-ubi9/simple/"


def test_resolve_rhoai_raises_when_skopeo_metadata_lookup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_file = write_conf(
        tmp_path,
        "konflux.cuda.conf",
        [
            "BASE_IMAGE=quay.io/aipcc/base-images/cuda-stable-ubi9:3.5",
            "PYLOCK_FLAVOR=cuda",
            "PRODUCT=rhoai",
        ],
    )

    def fail_inspect(base_image: str) -> dict[str, object]:
        raise resolver.IndexResolutionError(f"skopeo inspect failed for {base_image}")

    monkeypatch.setattr(
        resolver,
        "_inspect_base_image_config",
        fail_inspect,
        raising=False,
    )

    with pytest.raises(resolver.IndexResolutionError, match="skopeo inspect failed"):
        resolver.resolve_index_config(conf_file)


def test_resolve_rhoai_raises_when_image_labels_do_not_contain_index_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_file = write_conf(
        tmp_path,
        "konflux.cpu.conf",
        [
            "BASE_IMAGE=quay.io/aipcc/base-images/cpu:3.5.0-ea.2-1778762488",
            "PYLOCK_FLAVOR=cpu",
            "PRODUCT=rhoai",
        ],
    )
    monkeypatch.setattr(
        resolver,
        "_inspect_base_image_config",
        lambda base_image: inspect_config(labels={"description": "Red Hat AI Base Image without index metadata"}),
    )

    with pytest.raises(resolver.IndexResolutionError, match="missing supported index labels"):
        resolver.resolve_index_config(conf_file)
