"""Unit tests for build-args sync from versions_config.yml."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

import scripts.update_build_args_from_versions as updater  # noqa: E402


def _write_versions_config(
    path: Path,
    *,
    full_version: str = "3.6.0",
) -> None:
    config_text = textwrap.dedent(
        f"""\
        schema_version: 1

        release:
          full_version: "{full_version}"
          rhds_os_base: el9.6

        artifacts:
          base_image:
            cpu:
              rhds:
                acc_version: <full_version>
              odh:
                acc_version: latest

            cuda:
              minimal:
                rhds: {{ acc_version: 25.0 }}
                odh:  {{ acc_version: v25.0 }}
              pytorch:
                rhds: {{ acc_version: 25.0 }}
                odh:  {{ acc_version: v25.0 }}
              pytorch-llmcompressor:
                rhds: {{ acc_version: 25.0 }}
                odh:  {{ acc_version: v25.0 }}
              tensorflow:
                rhds: {{ acc_version: 24.9 }}
                odh:  {{ acc_version: v24.9 }}

            rocm:
              minimal:
                rhds: {{ acc_version: 8.0 }}
                odh:  {{ acc_version: v8.0 }}
              pytorch:
                rhds: {{ acc_version: 8.0 }}
                odh:  {{ acc_version: v8.0 }}
              tensorflow:
                rhds: {{ acc_version: 8.0 }}
                odh:  {{ acc_version: v8.0 }}
        """
    )

    path.write_text(config_text, encoding="utf-8")


@pytest.fixture
def release() -> updater.ReleaseConfig:
    return updater.ReleaseConfig(full_version="3.5.0", rhds_os_base="el9.6")


@pytest.fixture
def rhds_base_image() -> str:
    return "quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.1-1777919771"


def test_resolve_acc_version_uses_release_full_version_for_cpu_placeholder(release: updater.ReleaseConfig) -> None:
    assert updater.resolve_acc_version("<full_version>", release) == "3.5.0"


def test_parse_rhds_release_from_base_image_ea_tag(rhds_base_image: str) -> None:
    parsed = updater.parse_rhds_release_from_base_image(rhds_base_image)

    assert parsed.full_version == "3.5.0"
    assert parsed.phase == "ea1"


def test_parse_rhds_release_from_base_image_ga_tag() -> None:
    parsed = updater.parse_rhds_release_from_base_image(
        "quay.io/aipcc/base-images/cpu:3.5.0-1777920567"
    )

    assert parsed.full_version == "3.5.0"
    assert parsed.phase == ""


def test_rewrite_base_image_updates_accelerator_and_release_parts() -> None:
    release = updater.ReleaseConfig(full_version="3.6.0", rhds_os_base="el9.6")
    image = "quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.1-1777919771"

    assert updater.rewrite_base_image(image, "25.0", release, distribution="rhds") == (
        "quay.io/aipcc/base-images/cuda-25.0-el9.6:3.6.0-ea.1-1777919771"
    )


def test_rewrite_base_image_updates_rhds_os_base_when_requested() -> None:
    release = updater.ReleaseConfig(full_version="3.5.0", rhds_os_base="el9.7")
    image = "quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.1-1777919771"

    assert updater.rewrite_base_image(image, "13.0", release, distribution="rhds") == (
        "quay.io/aipcc/base-images/cuda-13.0-el9.7:3.5.0-ea.1-1777919771"
    )


def test_rewrite_base_image_uses_ga_override_without_phase_suffix() -> None:
    release = updater.ReleaseConfig(full_version="3.6.0", rhds_os_base="el9.6")
    image = "quay.io/aipcc/base-images/cpu:3.5.0-1777920567"

    assert updater.rewrite_base_image(
        image,
        "13.0",
        release,
        distribution="rhds",
        rhds_phase_override="ga",
    ) == (
        "quay.io/aipcc/base-images/cpu:3.6.0-1777920567"
    )


def test_rewrite_base_image_updates_odh_v_tag() -> None:
    release = updater.ReleaseConfig(full_version="3.6.0", rhds_os_base="el9.6")
    image = "quay.io/opendatahub/odh-base-image-cuda-py312-c9s:v13.0"

    assert updater.rewrite_base_image(image, "v25.0", release, distribution="odh") == (
        "quay.io/opendatahub/odh-base-image-cuda-py312-c9s:v25.0"
    )


def test_rewrite_base_image_uses_explicit_rhds_phase_override() -> None:
    release = updater.ReleaseConfig(full_version="3.6.0", rhds_os_base="el9.6")
    image = "quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.1-1777919771"

    assert updater.rewrite_base_image(
        image,
        "25.0",
        release,
        distribution="rhds",
        rhds_phase_override="ea.2",
    ) == "quay.io/aipcc/base-images/cuda-25.0-el9.6:3.6.0-ea.2-1777919771"


def test_rewrite_base_image_preserves_current_phase_when_version_is_not_higher() -> None:
    release = updater.ReleaseConfig(full_version="3.5.0", rhds_os_base="el9.6")
    image = "quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.2-1777919771"

    assert updater.rewrite_base_image(image, "25.0", release, distribution="rhds") == (
        "quay.io/aipcc/base-images/cuda-25.0-el9.6:3.5.0-ea.2-1777919771"
    )


def test_rewrite_conf_text_preserves_other_lines() -> None:
    original = (
        "# comment\n"
        "INDEX_URL=old-index\n"
        "BASE_IMAGE=old-image\n"
        "PROFILE=old-profile\n"
        "PYLOCK_FLAVOR=cuda\n"
    )

    updated = updater.rewrite_conf_text(
        original,
        {
            "BASE_IMAGE": "new-image",
            "PROFILE": "rhds",
        },
    )

    assert updated == (
        "# comment\n"
        "INDEX_URL=old-index\n"
        "BASE_IMAGE=new-image\n"
        "PROFILE=rhds\n"
        "PYLOCK_FLAVOR=cuda\n"
    )


def test_remove_conf_key_drops_assignment_line() -> None:
    original = (
        "# comment\n"
        "INDEX_URL=old-index\n"
        "BASE_IMAGE=old-image\n"
        "PYLOCK_FLAVOR=cuda\n"
    )

    assert updater.remove_conf_key(original, "INDEX_URL") == (
        "# comment\n"
        "BASE_IMAGE=old-image\n"
        "PYLOCK_FLAVOR=cuda\n"
    )


def test_ensure_conf_key_inserts_profile_before_pylock_flavor() -> None:
    original = (
        "INDEX_URL=old-index\n"
        "BASE_IMAGE=old-image\n"
        "PYLOCK_FLAVOR=cuda\n"
    )

    updated = updater.ensure_conf_key(original, "PROFILE", "rhds", before_key="PYLOCK_FLAVOR")

    assert updated == (
        "INDEX_URL=old-index\n"
        "BASE_IMAGE=old-image\n"
        "PROFILE=rhds\n"
        "PYLOCK_FLAVOR=cuda\n"
    )


def test_collect_conf_targets_classifies_synthetic_tree(tmp_path: Path) -> None:
    files = [
        tmp_path / "jupyter" / "minimal" / "ubi9-python-3.12" / "build-args" / "konflux.cuda.conf",
        tmp_path / "runtimes" / "rocm-pytorch" / "ubi9-python-3.12" / "build-args" / "rocm.conf",
        tmp_path / "rstudio" / "rhel9-python-3.12" / "build-args" / "konflux.cuda.conf",
        tmp_path / "base-images" / "build-args" / "cpu.conf",
        tmp_path / "base-images" / "build-args" / "rocm6.4.conf",
    ]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("INDEX_URL=dummy\nBASE_IMAGE=dummy\n", encoding="utf-8")

    targets = updater.collect_conf_targets(tmp_path)
    by_path = {target.path.relative_to(tmp_path).as_posix(): target for target in targets}

    assert len(targets) == 3
    assert by_path["jupyter/minimal/ubi9-python-3.12/build-args/konflux.cuda.conf"].flavor == "minimal"
    assert by_path["runtimes/rocm-pytorch/ubi9-python-3.12/build-args/rocm.conf"].flavor == "pytorch"
    assert by_path["rstudio/rhel9-python-3.12/build-args/konflux.cuda.conf"].flavor == "tensorflow"
    assert "base-images/build-args/cpu.conf" not in by_path
    assert "base-images/build-args/rocm6.4.conf" not in by_path


def test_load_versions_config_rejects_unexpected_keys(tmp_path: Path) -> None:
    bad_config = tmp_path / "versions_config.yml"
    bad_config.write_text(
        textwrap.dedent(
            """\
            schema_version: 1
            release:
              full_version: "3.5.0"
              rhds_os_base: el9.6
            artifacts:
              base_image:
                cpu:
                  rhds:
                    acc_version: <full_version>
                  odh:
                    acc_version: latest
                cuda:
                  minimal:
                    rhds: { acc_version: 13.0 }
                    odh: { acc_version: v13.0 }
                  pytorch:
                    rhds: { acc_version: 13.0 }
                    odh: { acc_version: v13.0 }
                  pytorch-llmcompressor:
                    rhds: { acc_version: 13.0 }
                    odh: { acc_version: v13.0 }
                  tensorflow:
                    rhds: { acc_version: 12.9 }
                    odh: { acc_version: v12.9 }
                rocm:
                  minimal:
                    rhds: { acc_version: 7.1 }
                    odh: { acc_version: v7.1 }
                  pytorch:
                    rhds: { acc_version: 7.1 }
                    odh: { acc_version: v7.1 }
                  tensorflow:
                    rhds: { acc_version: 7.1 }
                    odh: { acc_version: v7.1 }
                    unexpected:
                      acc_version: 999
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"Unexpected keys under .*: unexpected"):
        updater.load_versions_config(bad_config)


def test_load_versions_config_rejects_legacy_python_index_key(tmp_path: Path) -> None:
    bad_config = tmp_path / "versions_config.yml"
    bad_config.write_text(
        textwrap.dedent(
            """\
            schema_version: 1
            release:
              full_version: "3.5.0"
              rhds_os_base: el9.6
            python_index:
              rhds:
                mode: rh-index
                channel: auto
            artifacts:
              base_image:
                cpu:
                  rhds:
                    acc_version: <full_version>
                  odh:
                    acc_version: latest
                cuda:
                  minimal:
                    rhds: { acc_version: 13.0 }
                    odh: { acc_version: v13.0 }
                  pytorch:
                    rhds: { acc_version: 13.0 }
                    odh: { acc_version: v13.0 }
                  pytorch-llmcompressor:
                    rhds: { acc_version: 13.0 }
                    odh: { acc_version: v13.0 }
                  tensorflow:
                    rhds: { acc_version: 12.9 }
                    odh: { acc_version: v12.9 }
                rocm:
                  minimal:
                    rhds: { acc_version: 7.1 }
                    odh: { acc_version: v7.1 }
                  pytorch:
                    rhds: { acc_version: 7.1 }
                    odh: { acc_version: v7.1 }
                  tensorflow:
                    rhds: { acc_version: 7.1 }
                    odh: { acc_version: v7.1 }
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"Unexpected keys under root: python_index"):
        updater.load_versions_config(bad_config)


def test_main_check_returns_nonzero_when_updates_needed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_versions_config(tmp_path / "versions_config.yml")

    conf_file = tmp_path / "jupyter" / "minimal" / "ubi9-python-3.12" / "build-args" / "konflux.cuda.conf"
    conf_file.parent.mkdir(parents=True)
    conf_file.write_text(
        textwrap.dedent(
            """\
            INDEX_URL=https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA1/cuda13.0-ubi9-test/simple/
            BASE_IMAGE=quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.1-1777919771
            PROFILE=stale
            PYLOCK_FLAVOR=cuda
            """
        ),
        encoding="utf-8",
    )

    assert (
        updater.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(tmp_path / "versions_config.yml"),
                "--check",
            ]
        )
        == 1
    )
    output = capsys.readouterr().out
    assert "jupyter/minimal/ubi9-python-3.12/build-args/konflux.cuda.conf" in output
    assert "1 build-args file(s) need updates." in output
    assert "3.5.0-ea.1-1777919771" in conf_file.read_text(encoding="utf-8")


def test_main_updates_file_in_place(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_versions_config(tmp_path / "versions_config.yml")

    conf_file = tmp_path / "jupyter" / "minimal" / "ubi9-python-3.12" / "build-args" / "konflux.cuda.conf"
    conf_file.parent.mkdir(parents=True)
    conf_file.write_text(
        textwrap.dedent(
            """\
            INDEX_URL=https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA1/cuda13.0-ubi9-test/simple/
            BASE_IMAGE=quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.1-1777919771
            PROFILE=stale
            PYLOCK_FLAVOR=cuda
            """
        ),
        encoding="utf-8",
    )

    assert (
        updater.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(tmp_path / "versions_config.yml"),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Updated jupyter/minimal/ubi9-python-3.12/build-args/konflux.cuda.conf" in output
    text = conf_file.read_text(encoding="utf-8")
    assert "INDEX_URL=" not in text
    assert "BASE_IMAGE=quay.io/aipcc/base-images/cuda-25.0-el9.6:3.6.0-ea.1-1777919771" in text
    assert "PROFILE=rhds" in text


def test_main_removes_index_url_even_when_other_values_already_match(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_versions_config(tmp_path / "versions_config.yml")

    conf_file = tmp_path / "jupyter" / "minimal" / "ubi9-python-3.12" / "build-args" / "konflux.cuda.conf"
    conf_file.parent.mkdir(parents=True)
    conf_file.write_text(
        textwrap.dedent(
            """\
            INDEX_URL=https://console.redhat.com/api/pypi/public-rhai/rhoai/3.6-EA1/cuda25.0-ubi9-test/simple/
            BASE_IMAGE=quay.io/aipcc/base-images/cuda-25.0-el9.6:3.6.0-ea.1-1777919771
            PROFILE=rhds
            PYLOCK_FLAVOR=cuda
            """
        ),
        encoding="utf-8",
    )

    assert (
        updater.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(tmp_path / "versions_config.yml"),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Updated jupyter/minimal/ubi9-python-3.12/build-args/konflux.cuda.conf" in output
    assert "INDEX_URL=" not in conf_file.read_text(encoding="utf-8")


def test_main_uses_rhds_phase_override_for_release_bump(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_versions_config(tmp_path / "versions_config.yml")

    conf_file = tmp_path / "jupyter" / "minimal" / "ubi9-python-3.12" / "build-args" / "konflux.cuda.conf"
    conf_file.parent.mkdir(parents=True)
    conf_file.write_text(
        textwrap.dedent(
            """\
            INDEX_URL=https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA1/cuda13.0-ubi9-test/simple/
            BASE_IMAGE=quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.1-1777919771
            PROFILE=stale
            PYLOCK_FLAVOR=cuda
            """
        ),
        encoding="utf-8",
    )

    assert (
        updater.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(tmp_path / "versions_config.yml"),
                "--rhds-phase",
                "ea2",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Updated jupyter/minimal/ubi9-python-3.12/build-args/konflux.cuda.conf" in output
    text = conf_file.read_text(encoding="utf-8")
    assert "INDEX_URL=" not in text
    assert "BASE_IMAGE=quay.io/aipcc/base-images/cuda-25.0-el9.6:3.6.0-ea.2-1777919771" in text
    assert "PROFILE=rhds" in text


def test_main_updates_konflux_cpu_release_version_from_full_version(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_versions_config(tmp_path / "versions_config.yml")

    conf_file = tmp_path / "jupyter" / "minimal" / "ubi9-python-3.12" / "build-args" / "konflux.cpu.conf"
    conf_file.parent.mkdir(parents=True)
    conf_file.write_text(
        textwrap.dedent(
            """\
            INDEX_URL=https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA1/cpu-ubi9-test/simple/
            BASE_IMAGE=quay.io/aipcc/base-images/cpu:3.5.0-ea.1-1777920678
            PROFILE=stale
            PYLOCK_FLAVOR=cpu
            """
        ),
        encoding="utf-8",
    )

    assert (
        updater.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(tmp_path / "versions_config.yml"),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Updated jupyter/minimal/ubi9-python-3.12/build-args/konflux.cpu.conf" in output
    text = conf_file.read_text(encoding="utf-8")
    assert "INDEX_URL=" not in text
    assert "BASE_IMAGE=quay.io/aipcc/base-images/cpu:3.6.0-ea.1-1777920678" in text
    assert "PROFILE=rhds" in text


def test_main_keeps_current_phase_when_full_version_is_not_higher(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_versions_config(tmp_path / "versions_config.yml", full_version="3.5.0")

    conf_file = tmp_path / "jupyter" / "minimal" / "ubi9-python-3.12" / "build-args" / "konflux.cuda.conf"
    conf_file.parent.mkdir(parents=True)
    conf_file.write_text(
        textwrap.dedent(
            """\
            INDEX_URL=https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA2/cuda13.0-ubi9-test/simple/
            BASE_IMAGE=quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.2-1777919771
            PROFILE=stale
            PYLOCK_FLAVOR=cuda
            """
        ),
        encoding="utf-8",
    )

    assert (
        updater.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(tmp_path / "versions_config.yml"),
                "--rhds-phase",
                "ga",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Updated jupyter/minimal/ubi9-python-3.12/build-args/konflux.cuda.conf" in output
    text = conf_file.read_text(encoding="utf-8")
    assert "INDEX_URL=" not in text
    assert "BASE_IMAGE=quay.io/aipcc/base-images/cuda-25.0-el9.6:3.5.0-ea.2-1777919771" in text
    assert "PROFILE=rhds" in text


def test_main_updates_odh_conf_to_public_index(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_versions_config(tmp_path / "versions_config.yml")

    conf_file = tmp_path / "jupyter" / "minimal" / "ubi9-python-3.12" / "build-args" / "cpu.conf"
    conf_file.parent.mkdir(parents=True)
    conf_file.write_text(
        textwrap.dedent(
            """\
            INDEX_URL=https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA1/cpu-ubi9-test/simple/
            BASE_IMAGE=quay.io/opendatahub/odh-base-image-cpu-py312-c9s:latest
            PROFILE=stale
            PYLOCK_FLAVOR=cpu
            """
        ),
        encoding="utf-8",
    )

    assert (
        updater.main(
            [
                "--root",
                str(tmp_path),
                "--config",
                str(tmp_path / "versions_config.yml"),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Updated jupyter/minimal/ubi9-python-3.12/build-args/cpu.conf" in output
    text = conf_file.read_text(encoding="utf-8")
    assert "INDEX_URL=" not in text
    assert "PROFILE=odh" in text
