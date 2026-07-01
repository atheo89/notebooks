from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import types
from pathlib import Path

import pytest
import yaml

from manifests.tools.commit_env_refs import commit_field_key, parse_env_file
from tests import PROJECT_ROOT


def load_rollout():
    return importlib.import_module("manifests.tools.rollout_tag_on_imagestreams")


def prepare_repo_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    shutil.copy2(PROJECT_ROOT / "versions_config.yml", repo_root / "versions_config.yml")
    shutil.copytree(PROJECT_ROOT / "manifests" / "odh" / "base", repo_root / "manifests" / "odh" / "base")
    shutil.copytree(PROJECT_ROOT / "manifests" / "rhoai" / "base", repo_root / "manifests" / "rhoai" / "base")
    return repo_root


def write_release_version(repo_root: Path, full_version: str) -> None:
    config_path = repo_root / "versions_config.yml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["release"]["full_version"] = full_version
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def imagestream_tag_counts(base_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in sorted(base_dir.glob("*-imagestream.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        counts[path.name] = len(data["spec"]["tags"])
    return counts


def completed_process(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["skopeo"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def install_skopeo_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tags: tuple[str, ...] = ("3.3_ea1-v1.1", "3.4_ea1-v1.9", "3.4_ea2-v1.2"),
    digest: str = "sha256:" + "1" * 64,
    vcs_ref: str = "abcdef1234567890abcdef1234567890abcdef12",
) -> None:
    skopeo_inspect = importlib.import_module("manifests.tools.skopeo_inspect")

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        if cmd[:4] == ["skopeo", "list-tags", "--retry-times", "3"]:
            repository = cmd[4].removeprefix("docker://")
            return completed_process(stdout=json.dumps({"Repository": repository, "Tags": list(tags)}))
        if cmd[:2] == ["skopeo", "inspect"]:
            assert "--override-arch" in cmd
            assert cmd[cmd.index("--override-arch") + 1] == "amd64"
            assert "--override-os" in cmd
            assert cmd[cmd.index("--override-os") + 1] == "linux"
            image = cmd[-1].removeprefix("docker://")
            if "--config" in cmd:
                return completed_process(stdout=json.dumps({"config": {"Labels": {"vcs-ref": vcs_ref}}}))
            if image.endswith(":3.4_ea2-v1.2"):
                return completed_process(stdout=json.dumps({"Digest": digest}))
            return completed_process(returncode=1, stderr="manifest unknown")
        raise AssertionError(f"Unexpected subprocess command: {cmd!r}")

    monkeypatch.setattr(
        skopeo_inspect,
        "subprocess",
        types.SimpleNamespace(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired),
        raising=False,
    )


def test_main_rolls_out_rhoai_workbench_history_by_one_tag(tmp_path: Path) -> None:
    rollout = load_rollout()
    repo_root = prepare_repo_root(tmp_path)
    write_release_version(repo_root, "3.6.0")
    rhoai_base = repo_root / "manifests" / "rhoai" / "base"

    before_counts = imagestream_tag_counts(rhoai_base)

    assert rollout.main(["--root", str(repo_root), "--target", "rhoai"]) == 0

    after_counts = imagestream_tag_counts(rhoai_base)

    for filename, before_count in before_counts.items():
        if filename.startswith("runtime-"):
            assert after_counts[filename] == before_count
            continue
        assert after_counts[filename] == before_count + 1


def test_main_keeps_odh_workbench_history_at_two_tags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rollout = load_rollout()
    repo_root = prepare_repo_root(tmp_path)
    write_release_version(repo_root, "3.6.0")
    install_skopeo_stub(monkeypatch)
    odh_base = repo_root / "manifests" / "odh" / "base"

    before_counts = imagestream_tag_counts(odh_base)

    assert rollout.main(["--root", str(repo_root), "--target", "odh"]) == 0

    after_counts = imagestream_tag_counts(odh_base)

    for filename, before_count in before_counts.items():
        if filename.startswith("runtime-"):
            assert after_counts[filename] == before_count
            continue
        assert after_counts[filename] == 2


def test_main_updates_odh_env_files_and_kustomization_for_new_n_minus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rollout = load_rollout()
    repo_root = prepare_repo_root(tmp_path)
    write_release_version(repo_root, "3.6.0")
    install_skopeo_stub(monkeypatch)
    assert rollout.main(["--root", str(repo_root), "--target", "odh"]) == 0

    params_env = parse_env_file(repo_root / "manifests" / "odh" / "base" / "params.env")
    commit_env = parse_env_file(repo_root / "manifests" / "odh" / "base" / "commit.env")
    odh_base = repo_root / "manifests" / "odh" / "base"
    expected_param_keys = []
    expected_commit_keys = []
    for path in sorted(odh_base.glob("*-imagestream.yaml")):
        if path.name.startswith("runtime-"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        tag = data["spec"]["tags"][1]
        expected_param_keys.append(tag["from"]["name"].removesuffix("_PLACEHOLDER"))
        expected_commit_keys.append(tag["annotations"]["opendatahub.io/notebook-build-commit"].removesuffix("_PLACEHOLDER"))

    assert sorted(params_env) == sorted(expected_param_keys)
    assert not any(key.endswith("-2025-2") for key in params_env)

    for key, value in params_env.items():
        base_key = key.rsplit("-", 2)[0]
        repository = value.split("@", 1)[0]
        assert repository.rsplit("/", 1)[1] == base_key
        assert value == f"{repository}@{'sha256:' + '1' * 64}"

    workbench_commit_keys = [key for key in commit_env if key.startswith("odh-workbench-")]
    assert sorted(workbench_commit_keys) == sorted(expected_commit_keys)
    assert not any(key.endswith("-commit-2025-2") for key in workbench_commit_keys)
    for key in workbench_commit_keys:
        base_key, suffix = key.rsplit("-commit", 1)
        assert key == commit_field_key(base_key, suffix)
        assert commit_env[key] == "abcdef1"

    kustomization_text = (odh_base / "kustomization.yaml").read_text(encoding="utf-8")
    assert "data.odh-workbench-jupyter-minimal-cpu-py312-ubi9-3-4" in kustomization_text
    assert "data.odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-3-4" in kustomization_text
    assert "data.odh-workbench-jupyter-minimal-cpu-py312-ubi9-2025-2" not in kustomization_text
    assert "data.odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-2025-2" not in kustomization_text

    output_lines = capsys.readouterr().out.splitlines()
    assert output_lines[:2] == [
        "1/3 Updating imagestreams with new tag",
        "1/3 Imagestreams updated",
    ]
    params_start = output_lines.index("2/3 Updating the ODH params.env file")
    params_done = output_lines.index("2/3 ODH params.env file updated")
    progress_lines = output_lines[params_start + 1 : params_done]
    assert progress_lines
    expected_digest = "sha256:" + "1" * 64
    assert all(
        line.startswith("  [")
        and " commit=abcdef1 " in line
        and f" digest={expected_digest}" in line
        for line in progress_lines
    )
    commit_start = output_lines.index("3/3 Updating the ODH commit.env and kustomization.yaml files")
    commit_done = output_lines.index("3/3 ODH commit.env and kustomization.yaml updated")
    assert commit_start == params_done + 1
    assert commit_done == commit_start + 1
    assert "Updated manifests/odh/base/params.env" in output_lines
    assert "Updated manifests/odh/base/commit.env" in output_lines
    assert "Updated manifests/odh/base/kustomization.yaml" in output_lines


def test_main_rolls_rhoai_imagestreams_before_odh_step_two_when_target_all(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rollout = load_rollout()
    repo_root = prepare_repo_root(tmp_path)
    write_release_version(repo_root, "3.6.0")
    install_skopeo_stub(monkeypatch)
    rhoai_base = repo_root / "manifests" / "rhoai" / "base"
    before_counts = imagestream_tag_counts(rhoai_base)
    original_run_odh_params_step = rollout.run_odh_params_step
    observed_counts: dict[str, int] = {}

    def wrapped_run_odh_params_step(base_dir: Path, *, dry_run: bool, reporter):
        observed_counts.update(imagestream_tag_counts(rhoai_base))
        return original_run_odh_params_step(base_dir, dry_run=dry_run, reporter=reporter)

    monkeypatch.setattr(rollout, "run_odh_params_step", wrapped_run_odh_params_step)

    assert rollout.main(["--root", str(repo_root), "--target", "all"]) == 0

    assert observed_counts
    for filename, before_count in before_counts.items():
        if filename.startswith("runtime-"):
            assert observed_counts[filename] == before_count
            continue
        assert observed_counts[filename] == before_count + 1


def test_main_fails_when_odh_params_latest_repo_does_not_match_key_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rollout = load_rollout()
    repo_root = prepare_repo_root(tmp_path)
    write_release_version(repo_root, "3.6.0")
    install_skopeo_stub(monkeypatch)

    params_latest_path = repo_root / "manifests" / "odh" / "base" / "params-latest.env"
    params_latest_path.write_text(
        params_latest_path.read_text(encoding="utf-8").replace(
            "quay.io/opendatahub/odh-workbench-codeserver-datascience-cpu-py312-ubi9:3.5_ea1-v1.44",
            "quay.io/opendatahub/not-the-same-repo:3.5_ea1-v1.44",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match key base"):
        rollout.main(["--root", str(repo_root), "--target", "odh"])


def test_main_fails_when_no_previous_release_tag_matches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rollout = load_rollout()
    repo_root = prepare_repo_root(tmp_path)
    write_release_version(repo_root, "3.6.0")
    install_skopeo_stub(monkeypatch, tags=("3.3_ea1-v1.1",))

    with pytest.raises(ValueError, match="No published ODH tag found"):
        rollout.main(["--root", str(repo_root), "--target", "odh"])


def test_main_dry_run_skips_odh_env_sync_and_skopeo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rollout = load_rollout()
    repo_root = prepare_repo_root(tmp_path)
    write_release_version(repo_root, "3.6.0")
    odh_base = repo_root / "manifests" / "odh" / "base"
    before_counts = imagestream_tag_counts(odh_base)
    before_params = (odh_base / "params.env").read_text(encoding="utf-8")
    before_commit = (odh_base / "commit.env").read_text(encoding="utf-8")
    before_kustomization = (odh_base / "kustomization.yaml").read_text(encoding="utf-8")
    skopeo_inspect = importlib.import_module("manifests.tools.skopeo_inspect")

    def unexpected_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        raise AssertionError(f"dry-run should not call skopeo: {cmd!r}")

    monkeypatch.setattr(
        skopeo_inspect,
        "subprocess",
        types.SimpleNamespace(run=unexpected_run, TimeoutExpired=subprocess.TimeoutExpired),
        raising=False,
    )

    assert rollout.main(["--root", str(repo_root), "--target", "odh", "--dry-run"]) == 0

    assert imagestream_tag_counts(odh_base) == before_counts
    assert (odh_base / "params.env").read_text(encoding="utf-8") == before_params
    assert (odh_base / "commit.env").read_text(encoding="utf-8") == before_commit
    assert (odh_base / "kustomization.yaml").read_text(encoding="utf-8") == before_kustomization

    output_lines = capsys.readouterr().out.splitlines()
    assert output_lines[:2] == [
        "1/3 Updating imagestreams with new tag",
        "1/3 Imagestreams updated",
    ]
    assert not any("ODH params.env" in line for line in output_lines)
    assert not any("ODH commit.env" in line for line in output_lines)


def test_main_ignores_comment_only_differences(tmp_path: Path, capsys) -> None:
    rollout = load_rollout()
    repo_root = prepare_repo_root(tmp_path)
    write_release_version(repo_root, "3.4.0")
    target = repo_root / "manifests" / "rhoai" / "base" / "jupyter-rocm-minimal-notebook-imagestream.yaml"
    aligned_text = target.read_text(encoding="utf-8")
    original_text = aligned_text.replace(
        "# N - 2 Version of the image",
        "# N - 1 Version of the image",
        1,
    )
    target.write_text(original_text, encoding="utf-8")

    assert rollout.main(["--root", str(repo_root), "--target", "rhoai"]) == 0

    assert target.read_text(encoding="utf-8") == original_text
    assert capsys.readouterr().out == "ImageStream files already match the requested rollout.\n"
