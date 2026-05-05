from __future__ import annotations

from pathlib import Path

import scripts.dockerfile_fragments as fragments


def test_get_lockfile_for_public_dockerfile_prefers_odh_profile(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile.cpu"
    dockerfile.write_text("FROM scratch\n", encoding="utf-8")
    lock_dir = tmp_path / "uv.lock.d"
    lock_dir.mkdir()
    (lock_dir / "pylock.odh.cpu.toml").write_text('lock-version = "1.0"\n', encoding="utf-8")
    (lock_dir / "pylock.cpu.toml").write_text('lock-version = "1.0"\n', encoding="utf-8")

    assert fragments.get_lockfile_for_dockerfile(dockerfile) == lock_dir / "pylock.odh.cpu.toml"


def test_get_lockfile_for_konflux_dockerfile_prefers_rhds_profile(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile.konflux.cpu"
    dockerfile.write_text("FROM scratch\n", encoding="utf-8")
    lock_dir = tmp_path / "uv.lock.d"
    lock_dir.mkdir()
    (lock_dir / "pylock.rhds.cpu.toml").write_text('lock-version = "1.0"\n', encoding="utf-8")
    (lock_dir / "pylock.cpu.toml").write_text('lock-version = "1.0"\n', encoding="utf-8")

    assert fragments.get_lockfile_for_dockerfile(dockerfile) == lock_dir / "pylock.rhds.cpu.toml"
