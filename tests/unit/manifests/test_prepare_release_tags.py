from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml


_script_path = Path(__file__).resolve().parents[3] / "manifests" / "tools" / "prepare_release_tags.py"
_script_spec = importlib.util.spec_from_file_location("_prepare_release_tags", _script_path)
if _script_spec is None or _script_spec.loader is None:
    raise RuntimeError(f"Failed to load script from {_script_path}")
prepare_release_tags = importlib.util.module_from_spec(_script_spec)
sys.modules[_script_spec.name] = prepare_release_tags
_script_spec.loader.exec_module(prepare_release_tags)


def _write_workbench_imagestream(path: Path) -> None:
    path.write_text(
        """\
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  labels:
    opendatahub.io/notebook-image: "true"
  name: jupyter-minimal-notebook
spec:
  tags:
    - annotations:
        opendatahub.io/workbench-image-recommended: 'true'
        opendatahub.io/default-image: "true"
        opendatahub.io/notebook-build-commit: odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-n_PLACEHOLDER
      from:
        kind: DockerImage
        name: odh-workbench-jupyter-minimal-cpu-py312-ubi9-n_PLACEHOLDER
      name: "3.5"
      referencePolicy:
        type: Source
    - annotations:
        opendatahub.io/workbench-image-recommended: 'false'
        opendatahub.io/notebook-build-commit: odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-4_PLACEHOLDER
      from:
        kind: DockerImage
        name: odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-4_PLACEHOLDER
      name: "3.4"
      referencePolicy:
        type: Source
"""
    )


def _write_runtime_imagestream(path: Path) -> None:
    path.write_text(
        """\
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  labels:
    opendatahub.io/runtime-image: "true"
  name: runtime-minimal
spec:
  tags:
    - annotations:
        opendatahub.io/notebook-build-commit: odh-pipeline-runtime-minimal-cpu-py312-ubi9-commit-n_PLACEHOLDER
      from:
        kind: DockerImage
        name: odh-pipeline-runtime-minimal-cpu-py312-ubi9-n_PLACEHOLDER
      name: "latest"
      referencePolicy:
        type: Source
"""
    )


def test_released_suffix_for_tag() -> None:
    assert prepare_release_tags.released_suffix_for_tag("3.5") == "-3-5"


def test_rotate_env_mapping_uses_old_latest_values_for_new_released_suffix() -> None:
    latest = {
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-n": "quay.io/opendatahub/minimal:3.5",
        "odh-workbench-jupyter-datascience-cpu-py312-ubi9-n": "quay.io/opendatahub/ds:3.5",
    }

    rotated = prepare_release_tags.rotate_env_mapping(latest, released_suffix="-3-5")

    assert rotated == {
        "odh-workbench-jupyter-datascience-cpu-py312-ubi9-3-5": "quay.io/opendatahub/ds:3.5",
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-5": "quay.io/opendatahub/minimal:3.5",
    }


def test_prepare_odh_release_tags_rotates_workbench_and_skips_runtime(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "manifests" / "odh" / "base"
    base_dir.mkdir(parents=True)

    (base_dir / "params-latest.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-n=quay.io/opendatahub/minimal:3.5\n"
    )
    (base_dir / "commit-latest.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-n=abcdef0\n"
    )
    (base_dir / "params.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-4=quay.io/opendatahub/minimal:3.4\n"
    )
    (base_dir / "commit.env").write_text("odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-4=1234567\n")
    (base_dir / "kustomization.yaml").write_text("resources: []\n")

    workbench_path = base_dir / "jupyter-minimal-notebook-imagestream.yaml"
    runtime_path = base_dir / "runtime-minimal-imagestream.yaml"
    _write_workbench_imagestream(workbench_path)
    _write_runtime_imagestream(runtime_path)

    called: list[str] = []

    def _refresh_latest_commits() -> None:
        called.append("refresh")
        (base_dir / "commit-latest.env").write_text(
            "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-n=7654321\n"
        )

    def _generate_kustomization() -> None:
        called.append("kustomization")

    prepare_release_tags.prepare_odh_release_tags(
        base_dir,
        new_version="3.6",
        refresh_latest_commits=_refresh_latest_commits,
        generate_kustomization=_generate_kustomization,
    )

    assert called == ["refresh", "kustomization"]
    assert (base_dir / "params.env").read_text() == (
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-5=quay.io/opendatahub/minimal:3.5\n"
    )
    assert (base_dir / "commit.env").read_text() == (
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-5=abcdef0\n"
    )

    workbench = yaml.safe_load(workbench_path.read_text())
    runtime = yaml.safe_load(runtime_path.read_text())

    assert [tag["name"] for tag in workbench["spec"]["tags"]] == ["3.6", "3.5"]
    assert workbench["spec"]["tags"][0]["from"]["name"] == "odh-workbench-jupyter-minimal-cpu-py312-ubi9-n_PLACEHOLDER"
    assert (
        workbench["spec"]["tags"][1]["from"]["name"]
        == "odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-5_PLACEHOLDER"
    )
    assert (
        workbench["spec"]["tags"][1]["annotations"]["opendatahub.io/notebook-build-commit"]
        == "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-5_PLACEHOLDER"
    )
    assert workbench["spec"]["tags"][1]["annotations"]["opendatahub.io/workbench-image-recommended"] == "false"
    assert "opendatahub.io/default-image" not in workbench["spec"]["tags"][1]["annotations"]
    assert runtime["spec"]["tags"][0]["name"] == "latest"


def test_main_check_returns_nonzero_when_odh_updates_needed(tmp_path: Path, capsys) -> None:
    base_dir = tmp_path / "manifests" / "odh" / "base"
    base_dir.mkdir(parents=True)
    (base_dir / "params-latest.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-n=quay.io/opendatahub/minimal:3.5\n"
    )
    (base_dir / "commit-latest.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-n=abcdef0\n"
    )
    (base_dir / "params.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-4=quay.io/opendatahub/minimal:3.4\n"
    )
    (base_dir / "commit.env").write_text("odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-4=1234567\n")
    (base_dir / "kustomization.yaml").write_text("resources: []\n")
    _write_workbench_imagestream(base_dir / "jupyter-minimal-notebook-imagestream.yaml")
    _write_runtime_imagestream(base_dir / "runtime-minimal-imagestream.yaml")

    exit_code = prepare_release_tags.main(
        ["--variant", "odh", "--new-version", "3.6", "--check", "--root", str(tmp_path)]
    )

    assert exit_code == 1
    assert "manifests/odh/base/params.env" in capsys.readouterr().out


def test_main_rejects_rhoai_variant_for_first_pass(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="Only --variant odh"):
        prepare_release_tags.main(["--variant", "rhoai", "--new-version", "3.6", "--root", str(tmp_path)])


def test_prepare_odh_release_tags_excludes_runtime_params_but_keeps_runtime_commits(tmp_path: Path) -> None:
    base_dir = tmp_path / "manifests" / "odh" / "base"
    base_dir.mkdir(parents=True)
    (base_dir / "params-latest.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-n=quay.io/opendatahub/minimal:3.5\n"
        "odh-pipeline-runtime-minimal-cpu-py312-ubi9-n=quay.io/opendatahub/runtime-minimal:3.5\n"
    )
    (base_dir / "commit-latest.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-n=abcdef0\n"
        "odh-pipeline-runtime-minimal-cpu-py312-ubi9-commit-n=7654321\n"
    )
    (base_dir / "params.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-4=quay.io/opendatahub/minimal:3.4\n"
    )
    (base_dir / "commit.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-4=1234567\n"
        "odh-pipeline-runtime-minimal-cpu-py312-ubi9-commit-3-4=1111111\n"
    )
    (base_dir / "kustomization.yaml").write_text("resources: []\n")
    _write_workbench_imagestream(base_dir / "jupyter-minimal-notebook-imagestream.yaml")
    _write_runtime_imagestream(base_dir / "runtime-minimal-imagestream.yaml")

    prepare_release_tags.prepare_odh_release_tags(
        base_dir,
        new_version="3.6",
        refresh_latest_commits=lambda: None,
        generate_kustomization=lambda: None,
    )

    assert (base_dir / "params.env").read_text() == (
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-5=quay.io/opendatahub/minimal:3.5\n"
    )
    assert (base_dir / "commit.env").read_text() == (
        "odh-pipeline-runtime-minimal-cpu-py312-ubi9-commit-3-5=7654321\n"
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-5=abcdef0\n"
    )


def test_plan_odh_release_tags_rejects_multiple_existing_released_suffixes(tmp_path: Path) -> None:
    base_dir = tmp_path / "manifests" / "odh" / "base"
    base_dir.mkdir(parents=True)
    (base_dir / "params-latest.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-n=quay.io/opendatahub/minimal:3.5\n"
    )
    (base_dir / "commit-latest.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-n=abcdef0\n"
    )
    (base_dir / "params.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-4=quay.io/opendatahub/minimal:3.4\n"
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-3=quay.io/opendatahub/minimal:3.3\n"
    )
    (base_dir / "commit.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-4=1234567\n"
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-3=7654321\n"
    )
    _write_workbench_imagestream(base_dir / "jupyter-minimal-notebook-imagestream.yaml")
    _write_runtime_imagestream(base_dir / "runtime-minimal-imagestream.yaml")

    with pytest.raises(ValueError, match="multiple released suffixes"):
        prepare_release_tags.plan_odh_release_tags(base_dir, new_version="3.6")


def test_prepare_odh_release_tags_rolls_back_if_refresh_fails(tmp_path: Path) -> None:
    base_dir = tmp_path / "manifests" / "odh" / "base"
    base_dir.mkdir(parents=True)
    (base_dir / "params-latest.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-n=quay.io/opendatahub/minimal:3.5\n"
    )
    (base_dir / "commit-latest.env").write_text(
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-n=abcdef0\n"
    )
    original_params = "odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-4=quay.io/opendatahub/minimal:3.4\n"
    original_commit = "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-4=1234567\n"
    (base_dir / "params.env").write_text(original_params)
    (base_dir / "commit.env").write_text(original_commit)
    (base_dir / "kustomization.yaml").write_text("resources: []\n")
    workbench_path = base_dir / "jupyter-minimal-notebook-imagestream.yaml"
    runtime_path = base_dir / "runtime-minimal-imagestream.yaml"
    _write_workbench_imagestream(workbench_path)
    _write_runtime_imagestream(runtime_path)
    original_workbench = workbench_path.read_text()
    original_runtime = runtime_path.read_text()

    with pytest.raises(RuntimeError, match="boom"):
        prepare_release_tags.prepare_odh_release_tags(
            base_dir,
            new_version="3.6",
            refresh_latest_commits=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            generate_kustomization=lambda: None,
        )

    assert (base_dir / "params.env").read_text() == original_params
    assert (base_dir / "commit.env").read_text() == original_commit
    assert workbench_path.read_text() == original_workbench
    assert runtime_path.read_text() == original_runtime
