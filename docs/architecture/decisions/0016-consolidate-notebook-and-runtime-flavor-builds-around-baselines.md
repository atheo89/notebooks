# 16. Restructure notebook, runtime, and Code Server flavor builds around baseline directories

Date: 2026-07-24

## Status

Proposed

## Context

The repository currently models notebook and runtime images primarily as separate
directories per published flavor:

- `jupyter/datascience/ubi9-python-3.12/`
- `jupyter/pytorch/ubi9-python-3.12/`
- `jupyter/pytorch+llmcompressor/ubi9-python-3.12/`
- `jupyter/tensorflow/ubi9-python-3.12/`
- `jupyter/trustyai/ubi9-python-3.12/`
- `jupyter/rocm/pytorch/ubi9-python-3.12/`
- `jupyter/rocm/tensorflow/ubi9-python-3.12/`

`runtimes/` mirrors the same pattern with its own set of near-duplicate
Dockerfiles, lock files, and build arguments.

`codeserver/ubi9-python-3.12/` is another single-directory image definition
today. It is not split by accelerator in the same way as Jupyter, but it should
still follow the same explicit lock/build-arg structure so developers do not
need to learn a different model for one workbench family.

This layout has several drawbacks:

1. The leaf Dockerfiles repeat the same multi-stage build logic with only small
   differences in package set, accelerator, labels, and a few flavor-specific
   post-install steps.
2. Lock file regeneration is harder than it needs to be because the effective
   Python package index is partly inferred from directory layout, while product
   selection (`odh` vs `rhoai`) is expressed elsewhere.
3. ROCm variants are modeled as separate directory trees even though ROCm is an
   accelerator dimension, not a package flavor.
4. Workbench, runtime, and Code Server images use similar lock/build-arg
   patterns but do not share a common structure for package-flavor metadata and
   hook logic.

The need to simplify explicit locking from public PyPI versus the Red Hat index,
as discussed in [RHAIENG-6389](https://redhat.atlassian.net/browse/RHAIENG-6389),
made these problems more visible.

At the same time, `jupyter/minimal/` is materially different from the leaf
workbench images: it is itself a published image, has different Dockerfile
stages, and should remain separate even if it adopts the same naming and locking
conventions.

## Decision

1. Introduce **baseline directories** as the source of truth for flavor-driven
   image builds:
   - `jupyter/baseline/` for workbench images that extend the shared
     datascience stack
   - `runtimes/baseline/` for Elyra runtime images
   - `codeserver/baseline/` for Code Server workbench images

2. Model image builds using explicit build dimensions:
   - `PACKAGE_FLAVOR` — package set such as `datascience`, `pytorch`,
     `pytorch-llmcompressor`, `tensorflow`, or `trustyai`
   - `PYLOCK_FLAVOR` — accelerator-specific lock flavor such as `cpu`, `cuda`,
     or `rocm`
   - `INDEX` — Python package source, currently `pypi` or `rh_index`
   - `PRODUCT` — product variant (`odh` or `rhoai`)

3. Store package metadata and lock artifacts under each baseline using a single
   naming scheme:
   - `package-flavors/<package-flavor>/pyproject.toml`
   - `pylocks/pylock.<package-flavor>.<pylock-flavor>.<index>.toml`
   - `requirements/requirements.<package-flavor>.<pylock-flavor>.<index>.txt`

4. Parameterize each baseline Dockerfile so that a single Dockerfile per image
   family consumes:
   - the shared preparation stages for that image family
   - `PACKAGE_FLAVOR`
   - `PYLOCK_FLAVOR`
   - `INDEX`
   - product-specific build args such as `BASE_IMAGE`, labels, and `ROCM_PATH`

   `jupyter/baseline/`, `runtimes/baseline/`, and `codeserver/baseline/` use
   the same build-dimension model even when their Dockerfile bodies remain
   role-specific.

5. Treat ROCm as an accelerator-specific concern instead of a top-level
   directory split. Move ROCm behavior into hooks:
   - `accelerator-hooks/<accelerator>/`
   - `flavor-hooks/<package-flavor>/<accelerator>/`

   These hooks encapsulate cases such as:
   - creating ROCm `.so` symlinks
   - de-vendoring PyTorch ROCm libraries
   - TensorFlow ROCm protobuf compatibility setup
   - TrustyAI pre-install OS package requirements

6. Keep `jupyter/minimal/` as a separate Dockerfile family, but align it with
   the same build-dimension model and reuse shared accelerator hooks where
   practical.

7. Preserve existing published image names, manifests, tests, and target names
   during migration. The baseline becomes the build/lock source of truth first;
   published artifact names and test entry points can continue to use their
   current names until migration is complete.

## Target directory layout

The target state is three parallel baseline trees plus a separate
`jupyter/minimal/` tree:

```text
jupyter/baseline/
├── Dockerfile.konflux              # one multi-stage file for workbench leaves
├── build-args/
│   ├── odh.{flavor}.{accel}.conf   # INDEX=pypi
│   └── rhds.{flavor}.{accel}.conf  # INDEX=rh_index
├── package-flavors/
│   ├── datascience/pyproject.toml
│   ├── pytorch/pyproject.toml
│   ├── pytorch-llmcompressor/pyproject.toml
│   ├── tensorflow/pyproject.toml
│   └── trustyai/pyproject.toml
├── pylocks/
│   └── pylock.{flavor}.{accel}.{index}.toml
├── requirements/
│   └── requirements.{flavor}.{accel}.{index}.txt 
├── accelerator-hooks/              # depends ONLY on accel (cpu/cuda/rocm)
│   └── rocm/
│       ├── link-solibs.py          # move from old rocm-specific paths
│       └── post-pip.sh             # runs ROCm symlink fixups after install
├── flavor-hooks/                   # depends on (flavor x accel)
│   ├── pytorch/rocm/
│   │   ├── de-vendor-torch.py
│   │   └── post-pip.sh
│   ├── tensorflow/rocm/
│   │   ├── monkey_patch_protobuf_6x.py
│   │   ├── usercustomize.pth
│   │   └── post-pip.sh
│   └── trustyai/cpu/
│       └── pre-pip.sh             # installs OpenJDK before Python deps
├── scripts/
│   └── run-workbench-hooks.sh
└── utils/                          # Elyra/Kale shared files

runtimes/baseline/
├── Dockerfile.konflux              # one multi-stage file for runtime leaves
├── build-args/
│   ├── odh.{flavor}.{accel}.conf   # INDEX=pypi
│   └── rhds.{flavor}.{accel}.conf  # INDEX=rh_index
├── package-flavors/
│   ├── minimal/pyproject.toml
│   ├── datascience/pyproject.toml
│   ├── pytorch/pyproject.toml
│   ├── pytorch-llmcompressor/pyproject.toml
│   └── tensorflow/pyproject.toml
├── pylocks/
│   └── pylock.{flavor}.{accel}.{index}.toml
├── requirements/
│   └── requirements.{flavor}.{accel}.{index}.txt
├── accelerator-hooks/              # depends ONLY on accel (cpu/cuda/rocm)
│   └── rocm/
│       ├── link-solibs.py          # shared ROCm runtime fixups
│       └── post-pip.sh
├── flavor-hooks/                   # depends on (flavor x accel)
│   ├── pytorch/rocm/
│   │   ├── de-vendor-torch.py
│   │   └── post-pip.sh
│   └── tensorflow/rocm/
│       └── post-pip.sh
├── scripts/
│   └── run-runtime-hooks.sh
└── utils/                          # Elyra bootstrapper and runtime shared files

codeserver/baseline/
├── Dockerfile.konflux              # one Dockerfile for Code Server workbench leaves
├── build-args/
│   ├── odh.{flavor}.{accel}.conf   # INDEX=pypi
│   └── rhds.{flavor}.{accel}.conf  # INDEX=rh_index
├── package-flavors/
│   └── datascience/pyproject.toml  # CPU-only initially
├── pylocks/
│   └── pylock.{flavor}.{accel}.{index}.toml
├── requirements/
│   └── requirements.{flavor}.{accel}.{index}.txt
├── accelerator-hooks/              # only if Code Server later gains accel-specific logic
├── flavor-hooks/                   # only if a flavor needs extra Code Server setup
├── scripts/
│   └── run-codeserver-hooks.sh
└── utils/                          # VSIXs and Code Server shared assets
```

Notes:

- `jupyter/minimal/` remains separate because it is a distinct published image
  with different stages and responsibilities.
- `codeserver/baseline/` follows the same directory contract even if it is CPU
  only at first.
- Hook directories are created only when a flavor or accelerator actually needs
  custom behavior.

## Consequences

### Positive

- Lock generation becomes explicit: the selected package index is represented by
  `INDEX` instead of being inferred from directory layout.
- Notebook, runtime, and Code Server flavor definitions move closer to a
  single-source-of-truth model.
- Duplicate leaf Dockerfiles can be reduced substantially, especially across
  datascience, pytorch, pytorch-llmcompressor, tensorflow, and trustyai.
- ROCm-specific behavior becomes auditable and reusable instead of being hidden
  in separate `jupyter/rocm/*` and `runtimes/rocm-*` paths.
- Code Server adopts the same lock/build-arg conventions as the other image
  families instead of remaining a one-off structure.
- New flavors can be introduced by adding:
  - a `package-flavors/<flavor>/pyproject.toml`
  - matching build-args files
  - lock/requirements artifacts
  - optional hook directories only when needed

### Negative / risks

- Migration is cross-cutting: Makefile recipes, lockfile generators, tests,
  manifests, and developer workflows must all be updated carefully.
- The baseline Dockerfiles become more parameterized, so accidental drift in
  build args or file naming can break multiple flavors at once.
- During the transition, duplicate legacy and baseline trees may coexist and can
  drift unless one of them is declared authoritative.
- Hook ordering matters. A mistake in pre-pip versus post-pip versus
  accelerator-specific phases can cause behavior changes that are harder to spot
  than direct Dockerfile edits.

### Non-goals

- Merging `jupyter/minimal/` into the same Dockerfile as the workbench baseline
- Changing published image names or removing flavor-specific test notebooks in
  the same step
- Reusing the exact same Dockerfile body for Jupyter, runtimes, and Code Server
  when their role-specific setup remains different

## Migration plan

1. Make `jupyter/baseline/` the source of truth for workbench leaf package
   metadata and lock artifacts.
2. Add explicit `PACKAGE_FLAVOR`, `PYLOCK_FLAVOR`, `INDEX`, and when needed
   `ROCM_PATH`, to the baseline build-args files.
3. Move flavor-specific and accelerator-specific behavior into hook
   directories.
4. Update the lockfile generation tooling to produce baseline
   `pylock.<package-flavor>.<pylock-flavor>.<index>.toml` and matching
   `requirements` files.
5. Change Makefile image targets to build from the baseline Dockerfiles while
   preserving current target names.
6. Mirror the same structure in `runtimes/baseline/`.
7. Introduce `codeserver/baseline/` with the same lock/build-arg layout, even
   if it initially contains only the CPU datascience flavor.
8. Remove legacy flavor directories only after build, test, and manifest flows
   are proven equivalent.

## Notes from the prototype

An initial local prototype demonstrated that the baseline layout can be wired
with:

- explicit build-arg files per product/flavor/accelerator
- centralized `pylock` and `requirements` file naming
- hook discovery keyed by `PACKAGE_FLAVOR` and `PYLOCK_FLAVOR`

The prototype is only a structural proof and does not by itself complete the
repository-wide migration. Tooling and tests still need follow-up work before
this ADR should move from **Proposed** to **Accepted**.
