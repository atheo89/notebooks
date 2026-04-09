# Quick Start Guide

## I just want to understand what these are. Where do I start?

Read this in order:

1. **[BUNDLE_CONCEPTS_EXPLAINED.md](BUNDLE_CONCEPTS_EXPLAINED.md)** (10 min read)
   - Plain English, no jargon
   - Real-world examples
   - Analogies and comparisons

2. **[README.md](README.md)** (15 min read)
   - What customization bundles are
   - Overview of each bundle type
   - How they work together

## I want to use a bundle. What do I do?

**Prerequisites:**
- Have OpenDataHub/RHOAI deployed
- Access to Model Catalog
- A model you want to customize

**Steps:**

1. Open Model Catalog in Dashboard
2. Find a model → Click **"Customize"**
3. Workbench launches with your model
4. Jupyter extension shows bundle options
5. Pick a bundle → run the notebook

**For specific bundle guides:**
- LoRA fine-tuning → `fine-tuning-peft/README.md`
- Embedding tuning → `embedding-tuning-rag/README.md`
- Others → See `registry.yaml` for descriptions

## I want to understand the technical details

Read these in order:

1. **[CUSTOMIZE.md](../CUSTOMIZE.md)** (main integration guide)
   - Bundle structure
   - Key assumptions
   - Creating your own bundle
   - Integration points

2. **Individual bundle files:**
   - `fine-tuning-peft/metadata.yaml` - Configuration
   - `fine-tuning-peft/notebook.ipynb` - Implementation
   - `fine-tuning-peft/README.md` - User guide

3. **[registry.yaml](registry.yaml)**
   - Machine-readable metadata
   - Discovery tags
   - Recommended workflows

## I want to implement a new bundle

Follow this guide: [CUSTOMIZE.md - Creating Your Own Bundle](../CUSTOMIZE.md#creating-your-own-bundle)

Key steps:
1. Create directory: `customize-bundles/your-workflow/`
2. Write notebook (see `fine-tuning-peft/notebook.ipynb` as example)
3. Write metadata (see `fine-tuning-peft/metadata.yaml` as example)
4. Write README (see `fine-tuning-peft/README.md` as example)
5. Add to `registry.yaml`
6. Test thoroughly

## I want to integrate bundles with the Model Catalog

See [CUSTOMIZE.md - Integration with Model Catalog](../CUSTOMIZE.md#integration-with-model-catalog)

Key work needed:
1. Jupyter extension to read `registry.yaml`
2. Filter bundles by model type and hardware
3. Launch selected notebook with model context

## What bundle should I use?

| I want to... | Use this bundle |
|--------------|-----------------|
| Quick adaptation (hours) | LoRA fine-tuning |
| Maximum customization | Full fine-tuning |
| Better document search | Embedding tuning |
| Quick improvements (no training) | Prompt tuning |
| Evaluate quality automatically | LLM-as-Judge |
| Prepare/clean my data | Data processing |

## What do I read when?

```
DECISION TREE:

"I want to understand what these are"
  ↓
  → BUNDLE_CONCEPTS_EXPLAINED.md
  → README.md
  → SUMMARY.md

"I want to use a bundle"
  ↓
  → Individual bundle README.md
  → Run notebook.ipynb
  → Check metadata.yaml for requirements

"I want to build something"
  ↓
  → CUSTOMIZE.md
  → registry.yaml
  → Look at fine-tuning-peft/ as example
  → Create your own bundle

"I want to integrate with Model Catalog"
  ↓
  → CUSTOMIZE.md (Integration section)
  → registry.yaml (understand schema)
  → Build Jupyter extension to read registry
```

## Key Files

| File | Purpose | Read When |
|------|---------|-----------|
| **BUNDLE_CONCEPTS_EXPLAINED.md** | Understand concepts | First, no jargon |
| **README.md** | Overview of bundles | Want to know "what" |
| **CUSTOMIZE.md** | Integration guide | Want to know "how" |
| **registry.yaml** | Machine index | Building tooling |
| **SUMMARY.md** | Complete reference | Need full context |
| **fine-tuning-peft/notebook.ipynb** | Working code | Want to run something |
| **fine-tuning-peft/metadata.yaml** | Config schema | Building similar bundles |
| **fine-tuning-peft/README.md** | User guide | Want to understand LoRA |

## Common Questions

**Q: Where do I start?**
A: BUNDLE_CONCEPTS_EXPLAINED.md (10 min read, no jargon)

**Q: Can I run these notebooks now?**
A: Yes! Download `fine-tuning-peft/notebook.ipynb` or `embedding-tuning-rag/notebook.ipynb`
Set `/mnt/models/` and `/mnt/datasets/` paths, then run.

**Q: How do I customize hyperparameters?**
A: Edit the configuration cell in each notebook (Cell 2)

**Q: Can I add my own bundle?**
A: Yes! See CUSTOMIZE.md "Creating Your Own Bundle" section

**Q: Do I need GPU?**
A: For LoRA and full FT: yes (8-80 GB)
For others: no, CPU is fine

**Q: What if my model isn't HuggingFace?**
A: Place it at `/mnt/models/` and reference the local path

---

**Ready? Start with [BUNDLE_CONCEPTS_EXPLAINED.md](BUNDLE_CONCEPTS_EXPLAINED.md) →**
