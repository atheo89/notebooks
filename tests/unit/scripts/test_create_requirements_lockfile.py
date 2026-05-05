from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_stub_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    script_dir = repo_root / "scripts" / "lockfile-generators"
    helper_dir = script_dir / "helpers"
    helper_dir.mkdir(parents=True)

    source_script = REPO_ROOT / "scripts" / "lockfile-generators" / "create-requirements-lockfile.sh"
    (script_dir / "create-requirements-lockfile.sh").write_text(
        source_script.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (repo_root / "scripts" / "pylocks_generator.py").write_text(
        "# stubbed by tests\n",
        encoding="utf-8",
    )
    (helper_dir / "pylock-to-requirements.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[2]).write_text('generated\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (repo_root / "uv").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "mode=\"$3\"\n"
        "project_dir=\"$4\"\n"
        "mkdir -p \"$project_dir/uv.lock.d\"\n"
        "if [[ \"$mode\" == \"rh-index\" ]]; then\n"
        "  printf 'lock-version = \"1.0\"\\n' > \"$project_dir/uv.lock.d/pylock.rhds.cpu.toml\"\n"
        "else\n"
        "  printf 'lock-version = \"1.0\"\\n' > \"$project_dir/uv.lock.d/pylock.odh.cpu.toml\"\n"
        "fi\n",
        encoding="utf-8",
    )
    (repo_root / "uv").chmod(0o755)
    return repo_root


def test_create_requirements_lockfile_uses_profile_specific_rhds_artifacts(
    tmp_path: Path,
) -> None:
    repo_root = _write_stub_repo(tmp_path)
    project_dir = repo_root / "project"
    (project_dir / "build-args").mkdir(parents=True)
    (project_dir / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (project_dir / "build-args" / "konflux.cpu.conf").write_text(
        "INDEX_URL=https://example.invalid/simple/\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "bash",
            "scripts/lockfile-generators/create-requirements-lockfile.sh",
            "--pyproject-toml",
            "project/pyproject.toml",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (project_dir / "requirements.rhds.cpu.txt").read_text(encoding="utf-8") == "generated\n"
    assert not (project_dir / "requirements.cpu.txt").exists()
