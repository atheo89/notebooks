from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_script_path = Path(__file__).resolve().parents[3] / "scripts" / "update-commit-latest-env.py"
_script_spec = importlib.util.spec_from_file_location("_update_commit_latest_env", _script_path)
if _script_spec is None or _script_spec.loader is None:
    raise RuntimeError(f"Failed to load script from {_script_path}")
update_commit_latest_env = importlib.util.module_from_spec(_script_spec)
sys.modules[_script_spec.name] = update_commit_latest_env
_script_spec.loader.exec_module(update_commit_latest_env)


def test_merge_commit_latest_results_preserves_existing_values_for_unresolved_refs() -> None:
    images = [
        ("odh-workbench-jupyter-minimal-cpu-py312-ubi9-n", "quay.io/opendatahub/minimal:3.5"),
        ("odh-workbench-jupyter-pytorch-cuda-py312-ubi9-n", "quay.io/opendatahub/pytorch:3.5"),
    ]
    results = [
        ("quay.io/opendatahub/minimal:3.5", None),
        ("quay.io/opendatahub/pytorch:3.5", "1234567890abcdef"),
    ]
    existing = {
        "odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-n": "oldmin123456",
        "odh-workbench-jupyter-pytorch-cuda-py312-ubi9-commit-n": "oldpt11",
    }

    merged = update_commit_latest_env.merge_commit_latest_results(
        images,
        results,
        existing_commit_entries=existing,
        keep_existing_on_failure=True,
    )

    assert merged == [
        ("odh-workbench-jupyter-minimal-cpu-py312-ubi9-commit-n", "oldmin1"),
        ("odh-workbench-jupyter-pytorch-cuda-py312-ubi9-commit-n", "1234567"),
    ]


def test_merge_commit_latest_results_raises_when_missing_ref_has_no_existing_value() -> None:
    images = [("odh-workbench-jupyter-minimal-cpu-py312-ubi9-n", "quay.io/opendatahub/minimal:3.5")]
    results = [("quay.io/opendatahub/minimal:3.5", None)]

    with pytest.raises(ValueError, match="No refreshed or existing commit hash"):
        update_commit_latest_env.merge_commit_latest_results(
            images,
            results,
            existing_commit_entries={},
            keep_existing_on_failure=True,
        )
