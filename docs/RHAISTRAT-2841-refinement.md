# RHAISTRAT-2841 refinement

**Refinement verdict:** [RHAISTRAT-2841](https://redhat.atlassian.net/browse/RHAISTRAT-2841) is **not ready for implementation**. The current description understates the work, excludes essential customer enablement, and would break downstream consumers.

## Recommended Feature

**Title**

`Consolidate the OOTB workbench and runtime portfolio with a supported customization and migration path`

**Objective**

Replace the current preset-heavy portfolio with two recommended OOTB workbenches:

- **Universal Jupyter**
  - JupyterLab UI
  - Elyra/Kale extensions
  - Minimal supported package collection
  - Switchable workbench and Elyra pipeline-runtime modes
- **Minimal Code Server**
  - Productized from the existing `codeserver-baseline` image
  - Code Server, Python, notebook/kernel support, and essential development tooling
  - No data-science framework or accelerator package collection installed by default
  - ODH build based on CentOS Stream and public PyPI
  - RHOAI build based on the AIPCC CPU base and its corresponding Red Hat Python index

Customers requiring frameworks, accelerators, or specialized libraries must have a supported path based on curated package collections, AIPCC meta-packages, and an image helper.

This is a **multi-release, size-L initiative**, not the currently proposed M-sized dependency cleanup.

## Release strategy

```text
new images
  → 3.6 introduction and deprecation
    → downstream consumer migration
      → 3.7 retirement

Package contract → helper tooling
```



### RHOAI 3.6 — transition

- Introduce Universal Jupyter and Minimal Code Server.
- Keep the existing images available.
- Mark legacy presets as deprecated or non-recommended.
- Provide migration documentation and the package/image customization path.
- Validate upgrades of existing Notebook resources.
- Retain Minimal CUDA and ROCm images while downstream universal-training images depend on them.



### RHOAI 3.7 — cutover

- Make the two new images the only recommended OOTB choices.
- Remove legacy images from new-workbench selection only after migration gates pass.
- Define separately:
  - UI removal
  - ImageStream removal
  - build discontinuation
  - disconnected catalog removal
  - registry retention and support lifecycle

Existing workloads must continue restarting or have a documented, tested migration procedure.

## Proposed child Epics and Stories

1. **Develop and serve the Universal Jupyter and Minimal Code Server (epic 3.6)**

  **Universal Jupyter**
   Productionize the dual-mode approach explored by [PR #4110](https://github.com/opendatahub-io/notebooks/pull/4110). The PR is a useful prototype, but its PyPI/UBI image explicitly does not provide the required AIPCC production supply-chain contract.

   **Minimal Code Server proposal**
   Use the existing `[codeserver-baseline](../codeserver-baseline/ubi9-python-3.12/README.md)` implementation as the source of the new minimal Code Server image.
   Keep one functional image definition with two product supply-chain variants:
   The ODH and RHOAI variants should remain behaviorally equivalent. Differences are limited to the operating-system base, trusted package sources, architecture-specific resolved artifacts, product metadata, and release integration.

2. **Define package collections and the AIPCC meta-package contract (story)**

  Define supported collections, versioning, compatibility constraints, channels, connected/disconnected availability, ownership, and lifecycle.
   The existing [dependency meta-packages](../dependencies) provide a foundation, but not yet a complete customer-facing contract.

3. **Deliver the customer image helper (epic)**

  Productize the existing [custom-workbenches prototype](../custom-workbenches/README.md) into a supported workflow that:
  - Selects CPU, CUDA, or ROCm.
  - Selects compatible package collections.
  - Generates a reproducible image recipe.
  - Supports connected and disconnected environments.
  - Validates packages and reports incompatible combinations.
  - Produces diagnostic information suitable for customer support.

4. **Deliver the 3.6 deprecation and migration experience (story mainly documentation)**

  Cover UI messaging, documentation, existing Notebook behavior, rollback, N−1 compatibility, disconnected environments, and the difference between ephemeral runtime installation and persistent customization.

5. **Migrate downstream consumers (epic for the DevX team)**

  The distributed-workloads universal training images currently consume Minimal CPU, CUDA, and ROCm images. They must move to an agreed replacement base before those images are retired. See the [universal-training architecture overlay](https://github.com/opendatahub-io/architecture-context/blob/main/overlays/0013-universal-training-image-dual-purpose.md).
   Repository and organization-wide searches should identify any additional consumers.

6. **Retire and clean up legacy images in 3.7 (epic)**

  Remove legacy entries across notebook builds, ImageStreams, WorkspaceKinds, dashboard integration, disconnected catalogs, tests, documentation, Konflux components, and support/CVE ownership—only after downstream and customer migration gates pass.



## Immediate Epic breakdown: Develop Universal Jupyter and Minimal Code Server

This Epic should start immediately because it produces the two images required by the 3.6 transition. Its work follows the same concrete delivery flow for each image: develop and validate the image, collaborate with DevOps to build and publish it through the supported pipelines, and then serve it through the product manifests.

Package-helper development, legacy-image deprecation, downstream-consumer migration, and 3.7 retirement remain in their dedicated Epics.

### Task 1: Develop and validate Universal Jupyter for ODH and RHOAI

Develop one maintainable Universal Jupyter image definition with ODH and RHOAI supply-chain variants, using [PR #4110](https://github.com/opendatahub-io/notebooks/pull/4110) as an implementation reference rather than as the final production design.

This task includes the complete image-development workload:

- Define the minimal supported package manifest containing JupyterLab, Elyra/Kale, and the dependencies required by workbench and pipeline-runtime modes. Keep data-science frameworks and accelerator stacks outside the image.
- Use the ODH CPU base and public package index for ODH, and the pinned AIPCC CPU base and corresponding RH index for RHOAI. Generate the required product-specific locks, requirements, RPM inputs, and hermetic build inputs, with no public-PyPI fallback in RHOAI.
- Implement and harden the switch between interactive Jupyter workbench mode and Elyra pipeline-runtime mode. Define argument forwarding, signal handling, user-ID and filesystem permissions, certificates, proxy behavior, health probes, and shutdown behavior. The same image digest must support both modes.
- Validate JupyterLab startup, kernel discovery, notebook execution, terminals, persistent storage, Elyra/Kale extension loading, controller integration, routing, arbitrary supported user IDs, and clean shutdown.
- Validate the image through the supported Elyra pipeline flow, including pipeline submission, runtime startup, representative notebook/script execution, object-storage access, injected secrets and certificates, logs, failure reporting, and cleanup.
- Complete the required multi-architecture, FIPS, vulnerability, SBOM/provenance, hermetic-build, image-size, startup-time, and resource checks for both streams.

The task is complete when the same supported behavior is demonstrated in ODH and RHOAI using their respective trusted bases and package sources.

### Task 2: Onboard Universal Jupyter to the ODH and RHOAI build pipelines

Collaborate with DevOps to create the Universal Jupyter Konflux components, image repositories, and authoritative pipeline configuration for both streams. Configure component and repository names, source branches, output repositories, service accounts, AIPCC and subscription access where required, hermetic dependency prefetch, supported build platforms, Pipeline-as-Code triggers, image tests, push pipelines, signing, SBOM/provenance generation, and build notifications.

Ensure the ODH and RHOAI components run only in their intended environments. Pull-request and release builds must publish traceable artifacts to the correct product registries and expose sufficient evidence for release qualification and failure investigation.

### Task 3: Serve Universal Jupyter through the ODH and RHOAI product manifests

Add Universal Jupyter to both product streams using the images published by the onboarded pipelines. Update image metadata, version configuration, registry mappings, release inputs, ImageStreams or WorkspaceKinds, connected installation data, and disconnected mirroring data.

Expose Universal Jupyter as a new 3.6 workbench choice without removing or renaming the legacy images. Verify that the dashboard and notebook controller resolve the released image digest, start it in interactive workbench mode, and provide the same image for Elyra pipeline-runtime selection with the required mode configuration.

### Task 4: Develop and validate Minimal Code Server for RHOAI from `codeserver-baseline`

Enable the existing ODH `[codeserver-baseline](../codeserver-baseline/ubi9-python-3.12/README.md)` implementation as the RHOAI Minimal Code Server image. Do not create the image from Che-Code or by pruning `codeserver-datascience`.

Add the RHOAI build configuration using the pinned AIPCC CPU base and its corresponding RH index. Generate RH-index locks from the same direct dependency set used by ODH, add the required downstream RPM and generic-artifact inputs, and configure build-time and runtime `pip`/`uv` settings without public-PyPI fallback.

Preserve the baseline content boundary: Code Server, Python 3.12, package-management tools, terminal tooling, kernel and notebook enablement, debugging support, OpenShift integration, and supported VS Code extensions. Do not preinstall the data-science meta-package, AI frameworks, CUDA, or ROCm.

Validate startup, proxy integration, terminal access, Python and notebook execution, kernel discovery, debugging, extensions, persistent storage, routing, health probes, arbitrary supported user IDs, and clean shutdown. Complete the required multi-architecture, FIPS, vulnerability, SBOM/provenance, hermetic-build, image-size, startup-time, and resource checks. RHOAI must remain behaviorally equivalent to the ODH baseline while using its downstream trusted sources and metadata.

### Task 5: Onboard Minimal Code Server to the RHOAI build pipeline

Collaborate with DevOps to create the RHOAI Konflux component and image repository for Minimal Code Server through the authoritative downstream pipeline configuration. Configure the component name, source branch, output repository, AIPCC and subscription credentials, RH-index and RPM prefetch, supported build platforms, Pipeline-as-Code triggers, image tests, push pipeline, signing, SBOM/provenance generation, and build notifications.

Enable the RHOAI build matrix and confirm that pull-request and release builds run in the intended downstream environment, remain hermetic, publish signed and traceable artifacts to the correct registry, and expose the evidence needed for release qualification and failure investigation.

### Task 6: Serve Minimal Code Server through the RHOAI product manifests

Add Minimal Code Server to RHOAI using the image published by the onboarded downstream pipeline. Update image metadata, version configuration, registry mappings, release inputs, ImageStream or WorkspaceKind references, connected installation data, and disconnected mirroring data.

Expose Minimal Code Server as a new 3.6 workbench choice while retaining the existing Code Server image during the transition. Verify that the dashboard and notebook controller resolve the released digest and successfully launch the image with terminal, Python, kernel, notebook, debugging, extension, storage, routing, and health-probe functionality.

### Delivery flow

```text
Universal Jupyter development and validation
  → ODH and RHOAI pipeline onboarding
    → ODH and RHOAI manifest delivery

Minimal Code Server RHOAI development and validation
  → RHOAI pipeline onboarding
    → RHOAI manifest delivery
```

DevOps component and repository requests should begin as soon as image names, owners, bases, and target branches are agreed; onboarding does not need to wait for image implementation to finish. Manifest delivery requires stable repositories and successful release-candidate builds.

## Feature acceptance criteria

- Universal Jupyter works end-to-end as both:
  - Jupyter/Elyra/Kale workbench.
  - Elyra pipeline runtime.
- Minimal Code Server is delivered without the current data-science inventory.
- Minimal Code Server is implemented from `codeserver-baseline`, not from a pruned `codeserver-datascience` image.
- The same direct baseline dependency set produces both ODH and RHOAI variants.
- The RHOAI Minimal Code Server uses a pinned AIPCC CPU base and only its corresponding RH index for Python dependencies.
- The RHOAI build is hermetic and succeeds on every supported CPU architecture without reaching public PyPI.
- Code Server startup, terminal access, Python execution, kernel discovery, notebook execution, debugging, extensions, OpenShift routing, and health probes are validated downstream.
- The downstream image is included in connected and disconnected RHOAI installation paths with the correct product metadata.
- Both images meet multi-architecture, FIPS, vulnerability, hermetic-build, and disconnected requirements.
- Curated package collections can reproducibly build supported custom images.
- The image helper validates CPU/CUDA/ROCm and package compatibility.
- A 3.6 upgrade preserves existing workbenches and clearly communicates deprecation.
- Downstream consumers no longer depend on images scheduled for removal.
- The 3.7 catalog contains only the two intended OOTB workbenches after all migration gates pass.
- Rollback and support behavior are documented and tested.



## Corrections required in the current Jira

The following current assertions should be removed:

- **“No implementation work is needed for Code Server.”** The baseline implementation exists, but it is currently ODH-only. It requires an AIPCC base configuration, RH-index locks and runtime configuration, downstream RPM inputs, product metadata, CI/Konflux enablement, and release integration.
- **“The existing start script is already universal.”** The current minimal Jupyter image lacks the runtime packages and dual-mode contract.
- **Package collections and helper are out of scope.** They are required to make portfolio reduction usable and supportable.
- **Old images can simply disappear from ImageStreams.** Minimal CUDA/ROCm are active downstream build dependencies.
- **Runtime** `pip` **installation is a sufficient migration path.** Persistence, reproducibility, disconnected installation, and supportability are unresolved.
- **M / 3–5 sprint estimate.** The work spans at least two releases and multiple teams.



## Open clarification

Does “image helper assistant” mean productizing the existing interactive image-builder wizard, or delivering an AI-based support assistant in addition to that wizard?
