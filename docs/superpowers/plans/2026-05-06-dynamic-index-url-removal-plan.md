# Dynamic INDEX_URL Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove stored `INDEX_URL` from non-`base-images` build-args flows and make lock-generation consumers derive the effective index dynamically from `PROFILE` and `BASE_IMAGE`.

**Architecture:** Introduce one shared Python resolver for effective index URL computation, then refactor lock-generation consumers to use it. After consumers no longer depend on stored `INDEX_URL`, simplify the build-args sync and config schema so non-`base-images` `*.conf` files carry only `BASE_IMAGE`, `PROFILE`, and `PYLOCK_FLAVOR`.

**Tech Stack:** Python 3.14, bash, pytest, existing repo scripts under `scripts/`

---

## File Structure

### New files

- `scripts/index_url_resolver.py` — shared logic for deriving the effective index URL from `PROFILE` and `BASE_IMAGE`
- `tests/unit/scripts/test_index_url_resolver.py` — focused tests for ODH/RHDS URL resolution, release parsing, stream parsing, and production fallback

### Modified files

- `scripts/pylocks_generator.py` — stop reading `INDEX_URL` from confs; call the shared resolver instead
- `scripts/lockfile-generators/create-requirements-lockfile.sh` — stop sourcing `INDEX_URL`; call the shared resolver via Python
- `scripts/update_build_args_from_versions.py` — stop parsing/writing `python_index` / `INDEX_URL` for non-`base-images` targets
- `versions_config.yml` — remove `python_index` and update comments
- `tests/unit/scripts/test_pylocks_generator.py` — update to use `PROFILE` + `BASE_IMAGE` instead of stored `INDEX_URL`
- `tests/unit/scripts/test_create_requirements_lockfile.py` — update helper behavior to succeed without stored `INDEX_URL`
- `tests/unit/scripts/test_update_build_args_from_versions.py` — assert no `INDEX_URL` management for non-`base-images` targets
- `docs/build-args-and-lockfile-automation.md` — update implemented-flow doc after code changes
- `docs/packageupdate.md` — adjust user-facing flow if it references `INDEX_URL`

## Task 1: Shared Resolver

**Files:**
- Create: `scripts/index_url_resolver.py`
- Test: `tests/unit/scripts/test_index_url_resolver.py`

- [ ] **Step 1: Write the failing resolver tests**

```python
def test_resolve_effective_index_url_returns_public_pypi_for_odh() -> None:
    assert resolve_effective_index_url("odh", None) == "https://pypi.org/simple/"


def test_resolve_effective_index_url_builds_rhds_production_url() -> None:
    url = resolve_effective_index_url(
        "rhds",
        "quay.io/aipcc/base-images/cuda-12.9-el9.6:3.5.0-ea.1-1777919771",
        probe_url_exists=lambda _url: True,
    )
    assert url == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA1/cuda12.9-ubi9/simple/"


def test_resolve_effective_index_url_falls_back_to_test_when_production_missing() -> None:
    url = resolve_effective_index_url(
        "rhds",
        "quay.io/aipcc/base-images/cpu:3.5.0-ea.1-1777920678",
        probe_url_exists=lambda _url: False,
    )
    assert url == "https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA1/cpu-ubi9-test/simple/"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./uv run pytest tests/unit/scripts/test_index_url_resolver.py -q`
Expected: FAIL because `scripts/index_url_resolver.py` does not exist yet

- [ ] **Step 3: Write minimal resolver implementation**

```python
def resolve_effective_index_url(
    profile: str,
    base_image: str | None,
    *,
    probe_url_exists: Callable[[str], bool] = probe_url_exists,
) -> str:
    if profile == "odh":
        return "https://pypi.org/simple/"
    if profile != "rhds":
        raise ValueError(...)
    release = parse_rhds_release_from_base_image(base_image)
    stream_token = stream_token_from_base_image(base_image)
    production_url = build_rhds_index_url(release, stream_token, use_test=False)
    return production_url if probe_url_exists(production_url) else build_rhds_index_url(release, stream_token, use_test=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./uv run pytest tests/unit/scripts/test_index_url_resolver.py -q`
Expected: PASS

## Task 2: Refactor `pylocks_generator.py`

**Files:**
- Modify: `scripts/pylocks_generator.py`
- Modify: `tests/unit/scripts/test_pylocks_generator.py`
- Test: `tests/unit/scripts/test_index_url_resolver.py`

- [ ] **Step 1: Write the failing pylock generator tests**

```python
def test_get_index_flags_uses_profile_and_base_image_for_rhds(tmp_path: Path) -> None:
    build_args = tmp_path / "build-args"
    build_args.mkdir()
    (build_args / "konflux.cpu.conf").write_text(
        "BASE_IMAGE=quay.io/aipcc/base-images/cpu:3.5.0-ea.1-1777920678\nPROFILE=rhds\n",
        encoding="utf-8",
    )
    flags = pg.get_index_flags(tmp_path, "cpu", pg.IndexMode.rh_index, pg.LogBuffer())
    assert flags == ["--default-index=https://console.redhat.com/api/pypi/public-rhai/rhoai/3.5-EA1/cpu-ubi9-test/simple/?format=json"]
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `./uv run pytest tests/unit/scripts/test_pylocks_generator.py -q`
Expected: FAIL because current code still requires stored `INDEX_URL`

- [ ] **Step 3: Refactor generator to use the resolver**

```python
profile = read_conf_value(conf_file, "PROFILE")
base_image = read_conf_value(conf_file, "BASE_IMAGE")
index_url = resolve_effective_index_url(profile, base_image, probe_url_exists=...)
flags = [f"--default-index={ensure_json_format_param(index_url)}"]
```

- [ ] **Step 4: Run focused tests**

Run: `./uv run pytest tests/unit/scripts/test_index_url_resolver.py tests/unit/scripts/test_pylocks_generator.py -q`
Expected: PASS

## Task 3: Refactor requirements-lock helper

**Files:**
- Modify: `scripts/lockfile-generators/create-requirements-lockfile.sh`
- Modify: `tests/unit/scripts/test_create_requirements_lockfile.py`

- [ ] **Step 1: Write the failing helper test**

```python
(project_dir / "build-args" / "konflux.cpu.conf").write_text(
    "BASE_IMAGE=quay.io/aipcc/base-images/cpu:3.5.0-ea.1-1777920678\nPROFILE=rhds\n",
    encoding="utf-8",
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./uv run pytest tests/unit/scripts/test_create_requirements_lockfile.py -q`
Expected: FAIL because the shell script still expects `INDEX_URL`

- [ ] **Step 3: Implement helper-script resolver call**

```bash
PROFILE="${PROFILE:-}"
BASE_IMAGE="${BASE_IMAGE:-}"
REQUIREMENTS_INDEX_URL="$(
  python3 - <<'PY'
from scripts.index_url_resolver import resolve_effective_index_url
print(resolve_effective_index_url(profile=..., base_image=...))
PY
)"
```

- [ ] **Step 4: Run focused tests**

Run: `./uv run pytest tests/unit/scripts/test_create_requirements_lockfile.py tests/unit/scripts/test_pylocks_generator.py -q`
Expected: PASS

## Task 4: Simplify build-args sync and config schema

**Files:**
- Modify: `scripts/update_build_args_from_versions.py`
- Modify: `tests/unit/scripts/test_update_build_args_from_versions.py`
- Modify: `versions_config.yml`

- [ ] **Step 1: Write the failing updater tests**

```python
def test_main_updates_file_without_index_url(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    conf_file.write_text(
        "BASE_IMAGE=quay.io/aipcc/base-images/cuda-13.0-el9.6:3.5.0-ea.1-1777919771\nPROFILE=stale\nPYLOCK_FLAVOR=cuda\n",
        encoding="utf-8",
    )
    assert updater.main([...]) == 0
    text = conf_file.read_text(encoding="utf-8")
    assert "INDEX_URL=" not in text
    assert "PROFILE=rhds" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./uv run pytest tests/unit/scripts/test_update_build_args_from_versions.py -q`
Expected: FAIL because current schema and sync still manage `python_index` / `INDEX_URL`

- [ ] **Step 3: Implement minimal updater cleanup**

```python
ROOT_SCHEMA = {
    "schema_version": None,
    "release": RELEASE_SCHEMA,
    "artifacts": {"base_image": BASE_IMAGE_SCHEMA},
}

# in plan_updates(...)
replacements = {"PROFILE": profile}
if target.manage_base_image:
    replacements["BASE_IMAGE"] = resolved_base_image
```

- [ ] **Step 4: Run focused tests**

Run: `./uv run pytest tests/unit/scripts/test_update_build_args_from_versions.py -q`
Expected: PASS

## Task 5: Cleanup docs and verify repo state

**Files:**
- Modify: `docs/build-args-and-lockfile-automation.md`
- Modify: `docs/packageupdate.md`

- [ ] **Step 1: Update docs to remove stale `INDEX_URL` guidance**

```markdown
- non-`base-images` build-args no longer store `INDEX_URL`
- lock-generation consumers derive the effective index from `PROFILE` and `BASE_IMAGE`
- `base-images/build-args/*.conf` remain out of scope
```

- [ ] **Step 2: Run the focused verification set**

Run:

```bash
./uv run pytest tests/unit/scripts/test_index_url_resolver.py -q
./uv run pytest tests/unit/scripts/test_pylocks_generator.py -q
./uv run pytest tests/unit/scripts/test_create_requirements_lockfile.py -q
./uv run pytest tests/unit/scripts/test_update_build_args_from_versions.py -q
```

Expected: all tests pass

- [ ] **Step 3: Run the cleanup search**

Run: `rg '^INDEX_URL=' jupyter runtimes codeserver rstudio`
Expected: no matches

