# Using Baseline workbench images on Red Hat OpenShift AI (RHOAI)

Baseline images are lightweight **community-tier** workbenches and pipeline runtimes from the [Open Data Hub notebooks repository](https://github.com/opendatahub-io/notebooks). They are included in Open Data Hub (ODH) by default, but **not** in a standard RHOAI installation.

This guide explains what Baseline images are, when you might use them, and how to make them available on RHOAI—whether you are a cluster administrator or a regular user.

## What are Baseline images?

Baseline images are a small set of CPU workbench and runtime images built for Python 3.12. They are intended as a minimal starting point: you get a lean environment and add the packages you need.

| Image | Purpose |
| ----- | ------- |
| **Jupyter Baseline** | JupyterLab workbench |
| **Code Server Baseline** | VS Code–style workbench (code-server) |
| **Pipeline runtime Baseline** | Elyra / pipeline runtime image |

### Why they are not shipped with RHOAI by default

RHOAI focuses on **Red Hat–supported** workbench images (the **Secure** tier). Baseline images differ in ways that matter for support and compliance:

- **Tier:** **Community** — broader access to packages from the public Python index (PyPI), with you responsible for what you install on top.
- **Base OS:** **CentOS Stream 9 (`c9s`)**, not the RHEL-based images used for most RHOAI workbenches.
- **Registry:** Published to `quay.io/opendatahub` as part of the ODH community build, not the RHOAI operator bundle.

On ODH clusters, Baseline `ImageStream` objects are already in the operator manifests. On RHOAI, an administrator must **opt in** before they appear for everyone, or a user can **import** them individually (see below).

For technical details of the RHOAI overlay, see [manifests/rhoai/overlays/additional/baseline/README.md](../manifests/rhoai/overlays/additional/baseline/README.md).

## Choose your path

How you enable Baseline images depends on your permissions:

| Your role | Recommended approach | Where images appear in the dashboard |
| --------- | -------------------- | ------------------------------------ |
| **Cluster / OpenShift AI administrator** | [Way 1: Register ImageStreams for the whole platform](#way-1-cluster-administrator-register-baseline-imagestreams) | **Community** group |
| **Data scientist or project user** (no cluster admin) | [Way 2: Import images yourself](#way-2-project-user-import-baseline-images-manually) | **Custom** group |

The workbench behavior is the same in both cases. Only the **dashboard grouping and tier label** differ: the admin path uses official `ImageStream` metadata (`opendatahub.io/notebook-tier: community`), while manual import is treated as a **custom** image.

---

## Way 1: Cluster administrator — register Baseline ImageStreams

Use this when you can run `oc` with rights to modify the OpenShift AI **applications** namespace (by default `redhat-ods-applications`). One apply step registers all three Baseline images for every user on that cluster.

### Prerequisites

- `oc` CLI installed and logged in to the target cluster.
- Permission to create/update resources in the applications namespace (typically cluster admin or equivalent).
- `kustomize` **or** `oc`/`kubectl` with built-in kustomize support (the helper script will use what is available).

### Steps

1. **Log in to the cluster**

   ```bash
   oc login --token=<token> --server=<api-server-url>
   ```

   Confirm context:

   ```bash
   oc whoami
   oc project -q   # optional: check current project
   ```

2. **Clone the notebooks repository**

   ```bash
   git clone https://github.com/opendatahub-io/notebooks.git
   cd notebooks
   ```

   Use a branch or tag that matches your RHOAI release if your organization pins versions; otherwise `main` provides the current latest tags in the overlay.

3. **Optional: preview manifests (no cluster changes)**

   ```bash
   ./scripts/apply-baseline-imagestreams.sh preview
   ```

4. **Apply Baseline ImageStreams**

   ```bash
   ./scripts/apply-baseline-imagestreams.sh apply
   ```

   The script:

   - Renders the [baseline overlay](../manifests/rhoai/overlays/additional/baseline/) (including `ImageStream` definitions reused from ODH).
   - Applies them to `redhat-ods-applications` (override with `--applications-ns` if your deployment uses another namespace).
   - Restarts the `rhods-dashboard` deployment so the UI picks up the new images.

   Registration **makes images available** in the workbench and pipeline image selectors; it does not start any workbenches.

### After apply

- Baseline images should appear under the **Community** tier / group, with the same names as on ODH (`jupyter-baseline-notebook`, `code-server-baseline-notebook`).

### Remove Baseline images from the cluster

```bash
./scripts/apply-baseline-imagestreams.sh revert
```

This deletes the Baseline `ImageStream` resources and related config maps created by `apply`, and restarts the dashboard.

---

## Way 2: Project user — import Baseline images manually

Use this when you **do not** have cluster administrator access but still want to run Baseline images in your projects. You import each image through the OpenShift AI dashboard, the same flow as other custom workbench images.

### Prerequisites

- Access to OpenShift AI as a user who can create workbenches in at least one data science project.
- **Workbench image import** enabled for your environment (an administrator may need to turn on custom images under **Settings → Environment setup**). See [Enabling custom workbench images](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/creating-custom-workbench-images#enabling-custom-workbench-images-in-openshift-ai_custom-images) in the RHOAI documentation.
- Your cluster can pull from `quay.io/opendatahub` (network and registry policy).

### Image locations

Use the full image reference including a **tag** or **digest** from Quay (for example `quay.io/opendatahub/odh-workbench-jupyter-baseline-cpu-py312-c9s:<tag>`). Check the repository’s **Tags** tab for the latest supported tag.

| Workbench / runtime | Quay repository |
| ------------------- | --------------- |
| Jupyter Baseline | https://quay.io/repository/opendatahub/odh-workbench-jupyter-baseline-cpu-py312-c9s |
| Pipeline runtime Baseline | https://quay.io/repository/opendatahub/odh-pipeline-runtime-baseline-cpu-py312-c9s |
| Code Server Baseline | https://quay.io/repository/opendatahub/odh-workbench-codeserver-baseline-cpu-py312-c9s |

### Procedure

Follow the official RHOAI procedure: [Import a custom workbench image](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/creating-custom-workbench-images#importing-a-custom-workbench-image_custom-images).

Summary:

1. In the OpenShift AI dashboard, go to **Settings → Environment setup → Workbench images**.
2. Click **Import new image**.
3. In **Image location**, enter the Quay URL with tag or digest (for example `quay.io/opendatahub/odh-workbench-jupyter-baseline-cpu-py312-c9s:3.6-v1.50`).
4. Set a **Name** (and optional description) you will recognize when creating workbenches.
5. Complete any optional software or package metadata, then confirm the import.
6. Repeat for each Baseline variant you need (Jupyter, Code Server, and/or pipeline runtime).

Imported images appear under the **Custom** tier in the image selector. Functionality matches the community ImageStreams from Way 1; only the UI classification differs.

**Support note:** Red Hat documents support for the *import mechanism* for custom images, not the contents of community Baseline images. You are responsible for validating that the image meets your project’s requirements.

---

## Related documentation

- [Baseline overlay (admin reference)](../manifests/rhoai/overlays/additional/baseline/README.md)
- [RHOAI additional notebooks overlay](../manifests/rhoai/overlays/additional/README.md)
- [Workbench ImageStream annotations (tiers and dashboard behavior)](workbench-imagestreams.md)
- [RHOAI: Create custom workbench images](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/creating-custom-workbench-images)
