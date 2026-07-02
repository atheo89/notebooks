from __future__ import annotations

import importlib
import json
import subprocess
import types

import pytest

from manifests.tools.skopeo_inspect import InspectedImage, inspect_image


def load_rollout():
    return importlib.import_module("manifests.tools.rollout_tag_on_imagestreams")


def completed_process(*, stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["skopeo"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_inspect_image_uses_no_tags_and_returns_digest_and_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        return completed_process(
            stdout=json.dumps(
                {
                    "Digest": "sha256:" + "a" * 64,
                    "Labels": {"vcs-ref": "abcdef1234567890abcdef1234567890abcdef12"},
                }
            )
        )

    skopeo_inspect = importlib.import_module("manifests.tools.skopeo_inspect")
    monkeypatch.setattr(
        skopeo_inspect,
        "subprocess",
        types.SimpleNamespace(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired),
        raising=False,
    )

    result = inspect_image("quay.io/example/repo:tag")

    assert result == InspectedImage(
        digest="sha256:" + "a" * 64,
        payload={
            "Digest": "sha256:" + "a" * 64,
            "Labels": {"vcs-ref": "abcdef1234567890abcdef1234567890abcdef12"},
        },
    )
    assert captured == [
        [
            "skopeo",
            "inspect",
            "--retry-times",
            "3",
            "--no-tags",
            "--override-arch",
            "amd64",
            "--override-os",
            "linux",
            "docker://quay.io/example/repo:tag",
        ]
    ]


def test_extract_short_vcs_ref_accepts_root_labels() -> None:
    rollout = load_rollout()

    commit_sha = rollout.extract_short_vcs_ref(
        {"Labels": {"vcs-ref": "abcdef1234567890abcdef1234567890abcdef12"}},
        "quay.io/example/repo@sha256:abc",
    )

    assert commit_sha == "abcdef1"
