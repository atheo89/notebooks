from __future__ import annotations

import manifests.tools.update_imagestream_annotations_from_pylock as updater


def test_pylock_candidate_rel_paths_prefers_odh_profile_for_odh() -> None:
    notebook_dir = updater.ROOT / "jupyter" / "minimal" / "ubi9-python-3.12"

    candidates = updater.pylock_candidate_rel_paths(notebook_dir, "cpu", "odh")

    assert candidates[:4] == [
        "jupyter/minimal/ubi9-python-3.12/uv.lock.d/pylock.odh.cpu.toml",
        "jupyter/minimal/ubi9-python-3.12/uv.lock.d/pylock.cpu.toml",
        "jupyter/minimal/ubi9-python-3.12/pylock.toml",
        "jupyter/minimal/ubi9-python-3.12/requirements.odh.cpu.txt",
    ]


def test_pylock_candidate_rel_paths_prefers_rhds_profile_for_rhoai() -> None:
    notebook_dir = updater.ROOT / "jupyter" / "minimal" / "ubi9-python-3.12"

    candidates = updater.pylock_candidate_rel_paths(notebook_dir, "cpu", "rhoai")

    assert candidates[:4] == [
        "jupyter/minimal/ubi9-python-3.12/uv.lock.d/pylock.rhds.cpu.toml",
        "jupyter/minimal/ubi9-python-3.12/uv.lock.d/pylock.cpu.toml",
        "jupyter/minimal/ubi9-python-3.12/pylock.toml",
        "jupyter/minimal/ubi9-python-3.12/requirements.rhds.cpu.txt",
    ]
