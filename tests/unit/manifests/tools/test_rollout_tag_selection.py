from __future__ import annotations

import importlib

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
