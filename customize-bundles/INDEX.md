# Customization Bundles - Complete Index

Welcome! This directory contains everything you need to understand, use, and build model customization bundles for the OpenDataHub Model Catalog "Customize" action.

## 📚 Documentation (Read These First)

Start here based on your role:

### For Everyone
- **[QUICK_START.md](QUICK_START.md)** - Decision tree for what to read
- **[BUNDLE_CONCEPTS_EXPLAINED.md](BUNDLE_CONCEPTS_EXPLAINED.md)** - No jargon, plain English explanations

### For Users
- **[README.md](README.md)** - What bundles are and how to use them
- **[fine-tuning-peft/README.md](fine-tuning-peft/README.md)** - LoRA fine-tuning guide
- **[embedding-tuning-rag/README.md](embedding-tuning-rag/README.md)** - Embedding tuning guide

### For Developers & Integrators
- **[../CUSTOMIZE.md](../CUSTOMIZE.md)** - Main integration guide (in notebooks root)
- **[SUMMARY.md](SUMMARY.md)** - Complete technical reference
- **[registry.yaml](registry.yaml)** - Machine-readable bundle index

## 🎯 Bundles

### 1. Fine-Tuning with PEFT (LoRA) ✅ READY
- **Directory:** `fine-tuning-peft/`
- **Status:** Fully implemented
- **What:** Train only 1% of model parameters
- **Time:** 2-4 hours
- **GPU:** 8-16 GB
- **Start:** [fine-tuning-peft/README.md](fine-tuning-peft/README.md)

**Files:**
- `notebook.ipynb` - Runnable notebook (600+ lines)
- `metadata.yaml` - Configuration metadata
- `README.md` - User guide

---

### 2. Embedding Tuning for RAG ✅ READY
- **Directory:** `embedding-tuning-rag/`
- **Status:** Fully implemented
- **What:** Customize embeddings for document retrieval
- **Time:** 30 minutes
- **GPU:** Optional (CPU works!)
- **Start:** [embedding-tuning-rag/README.md](embedding-tuning-rag/README.md)

**Files:**
- `notebook.ipynb` - Runnable notebook (400+ lines)
- `metadata.yaml` - Configuration metadata
- `README.md` - User guide

---

### 3. Open Source Fine-Tuning (OSFT) 📋 DOCUMENTED
- **Directory:** `fine-tuning-osft/`
- **Status:** In registry, notebook needed
- **What:** Full model fine-tuning
- **Time:** 24-80 hours
- **GPU:** 24-80 GB (expensive!)
- **Start:** `registry.yaml` (see bundle entry)

---

### 4. Prompt Tuning & Experimentation 📋 DOCUMENTED
- **Directory:** `prompt-tuning/`
- **Status:** In registry, notebook needed
- **What:** Optimize prompts without training
- **Time:** 1-2 hours
- **GPU:** Not needed
- **Start:** `registry.yaml` (see bundle entry)

---

### 5. Evaluation with LLM-as-Judge 📋 DOCUMENTED
- **Directory:** `evaluation/`
- **Status:** In registry, notebook needed
- **What:** Automate quality evaluation
- **Time:** 30 minutes for 1000 outputs
- **GPU:** Not needed
- **Start:** `registry.yaml` (see bundle entry)

---

### 6. Data Processing & Synthetic Data Generation 📋 DOCUMENTED
- **Directory:** `data-processing-sdg/`
- **Status:** In registry, notebook needed
- **What:** Clean and augment training data
- **Time:** 1-2 hours
- **GPU:** Not needed
- **Start:** `registry.yaml` (see bundle entry)

---

## 📋 Configuration & Metadata

### registry.yaml
**What:** Machine-readable index of all bundles

**Used by:**
- Jupyter extension (bundle discovery)
- Model Catalog (recommendations)
- Documentation generators

**Contains:**
- Bundle metadata (requirements, compatibility)
- Input/output specifications
- Hyperparameter ranges
- Discoverability tags
- Recommended workflow chains

**Read this if:** Building integration tooling or Jupyter extension

---

## 🗂️ Directory Structure

```
customize-bundles/
├── INDEX.md                           ← You are here
├── QUICK_START.md                     ← Decision tree
├── BUNDLE_CONCEPTS_EXPLAINED.md       ← Plain English
├── README.md                          ← Overview
├── SUMMARY.md                         ← Complete reference
├── registry.yaml                      ← Machine index
│
├── fine-tuning-peft/
│   ├── notebook.ipynb                 ✅
│   ├── metadata.yaml                  ✅
│   └── README.md                      ✅
│
├── embedding-tuning-rag/
│   ├── notebook.ipynb                 ✅
│   ├── metadata.yaml                  ✅
│   └── README.md                      ✅
│
├── prompt-tuning/
│   └── (needs notebook)               📋
│
├── evaluation/
│   └── (needs notebook)               📋
│
├── data-processing-sdg/
│   └── (needs notebook)               📋
│
└── fine-tuning-osft/
    └── (needs notebook)               📋
```

**Legend:** ✅ = Implemented | 📋 = In registry, needs notebook

---

## 🚀 Quick Navigation

### I want to...

**Understand what these bundles are**
→ [QUICK_START.md](QUICK_START.md) → [BUNDLE_CONCEPTS_EXPLAINED.md](BUNDLE_CONCEPTS_EXPLAINED.md)

**Use a bundle to fine-tune my model**
→ [fine-tuning-peft/README.md](fine-tuning-peft/README.md) → [fine-tuning-peft/notebook.ipynb](fine-tuning-peft/notebook.ipynb)

**Improve my RAG system's retrieval**
→ [embedding-tuning-rag/README.md](embedding-tuning-rag/README.md) → [embedding-tuning-rag/notebook.ipynb](embedding-tuning-rag/notebook.ipynb)

**Integrate bundles with Model Catalog**
→ [../CUSTOMIZE.md](../CUSTOMIZE.md) → [registry.yaml](registry.yaml)

**Create my own customization bundle**
→ [../CUSTOMIZE.md#creating-your-own-bundle](../CUSTOMIZE.md#creating-your-own-bundle)

**Build the Jupyter extension**
→ [registry.yaml](registry.yaml) → [SUMMARY.md](SUMMARY.md)

**See complete technical details**
→ [SUMMARY.md](SUMMARY.md)

**Find all hyperparameter options**
→ [fine-tuning-peft/metadata.yaml](fine-tuning-peft/metadata.yaml)

**See example Jupyter notebook code**
→ [fine-tuning-peft/notebook.ipynb](fine-tuning-peft/notebook.ipynb)

---

## 📊 At a Glance

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| **QUICK_START.md** | Doc | 150 | Decision tree |
| **BUNDLE_CONCEPTS_EXPLAINED.md** | Doc | 500+ | No-jargon guide |
| **README.md** | Doc | 600+ | Bundle overview |
| **CUSTOMIZE.md** | Doc | 600+ | Integration guide |
| **SUMMARY.md** | Doc | 800+ | Complete reference |
| **registry.yaml** | Config | 400+ | Machine index |
| **fine-tuning-peft/notebook.ipynb** | Code | 600+ | LoRA implementation |
| **fine-tuning-peft/metadata.yaml** | Config | 100+ | LoRA metadata |
| **fine-tuning-peft/README.md** | Doc | 300+ | LoRA user guide |
| **embedding-tuning-rag/notebook.ipynb** | Code | 400+ | Embedding implementation |
| **embedding-tuning-rag/metadata.yaml** | Config | 80+ | Embedding metadata |
| **embedding-tuning-rag/README.md** | Doc | 250+ | Embedding user guide |

**Total:** 3000+ lines of documentation, configuration, and working code

---

## 🎓 Learning Path

```
BEGINNER
  ↓
Read: QUICK_START.md (5 min)
Read: BUNDLE_CONCEPTS_EXPLAINED.md (15 min)
Read: README.md (20 min)
  ↓
Pick a bundle (LoRA or Embeddings)
Read: Bundle-specific README.md
  ↓
Run: notebook.ipynb
  ↓
SUCCESS: Customized model!

    ↓

INTERMEDIATE
  ↓
Understand: Bundle structure
Read: individual metadata.yaml files
Read: SUMMARY.md for details
  ↓
Explore: notebook.ipynb code
Understand: hyperparameters
Modify: for your use case

    ↓

ADVANCED
  ↓
Create: Your own bundle
Read: CUSTOMIZE.md "Creating Your Own Bundle"
Follow: Structure from fine-tuning-peft/
Test: Your new bundle
Contribute: Back to community
```

---

## 📞 Support

**Questions about bundles?**
- Check [QUICK_START.md](QUICK_START.md) decision tree
- Read relevant README.md for bundle type
- See BUNDLE_CONCEPTS_EXPLAINED.md for plain-English explanations

**Technical questions?**
- Check [SUMMARY.md](SUMMARY.md)
- Read [../CUSTOMIZE.md](../CUSTOMIZE.md)
- Check `metadata.yaml` for specific requirements

**Want to build a bundle?**
- Follow guide in [../CUSTOMIZE.md#creating-your-own-bundle](../CUSTOMIZE.md#creating-your-own-bundle)
- Use `fine-tuning-peft/` as reference implementation
- Ask questions in GitHub issues

**Found a bug?**
- Report in GitHub issues
- Include: bundle name, error message, steps to reproduce

---

## ✅ Status

| Aspect | Status |
|--------|--------|
| **Framework complete** | ✅ |
| **LoRA bundle** | ✅ Fully implemented |
| **Embedding bundle** | ✅ Fully implemented |
| **Other bundles** | 📋 In registry, need notebooks |
| **Documentation** | ✅ Complete (3000+ lines) |
| **Registry** | ✅ Complete |
| **Ready for integration** | ✅ YES |

---

## 🔗 Related Files

**In notebooks/ root:**
- `CUSTOMIZE.md` - Main integration guide
- `README.md` - Should reference CUSTOMIZE.md

**In notebooks/jupyter/**
- Various workbench images (used by bundles)

**Related projects:**
- Model Catalog UI
- Jupyter extensions
- Workbench controller

---

**Last updated:** April 9, 2024
**For:** RHAISTRAT-1182 - Customize action in Model Catalog
**Status:** ✅ COMPLETE - Ready for integration
