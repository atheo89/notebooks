from __future__ import annotations

import asyncio
import importlib
import importlib.util
from pathlib import Path

from tests import PROJECT_ROOT

def load_updater():
    spec = importlib.util.spec_from_file_location(
        "scripts.update_commit_latest_env",
        PROJECT_ROOT / "scripts" / "update-commit-latest-env.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_writes_only_workbench_commit_latest_entries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    updater = load_updater()
    repo_root = tmp_path / "repo"
    base_dir = repo_root / "manifests" / "odh" / "base"
    base_dir.mkdir(parents=True)
    (base_dir / "params-latest.env").write_text(
        "\n".join(
            [
                "odh-workbench-jupyter-minimal-cpu-py312-ubi9-n=quay.io/opendatahub/workbench:latest",
                "odh-pipeline-runtime-minimal-cpu-py312-ubi9-n=quay.io/opendatahub/runtime:latest",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(updater, "PROJECT_ROOT", repo_root)
    inspected_images: list[str] = []

    async def fake_inspect(images_to_inspect):
        images = list(images_to_inspect)
        inspected_images.extend(images)
        return [(image, "abcdef1234567890") for image in images]

    monkeypatch.setattr(updater, "inspect", fake_inspect)

    asyncio.run(updater.main())

    assert inspected_images == ["quay.io/opendatahub/workbench:latest"]
    assert (base_dir / "commit-latest.env").read_text(encoding="utf-8") == (
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-n=abcdef1\n"
    )
