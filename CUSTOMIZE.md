# Customize Bundles Guide

This document explains the Customize Bundles framework — curated, runnable examples for model customization workflows integrated with the Model Catalog.

## Quick Start

### For Users

1. Open Model Catalog in OpenDataHub Dashboard
2. Select a model → click **"Customize"**
3. A preconfigured Workbench launches with your selected model
4. Jupyter extension presents available customization bundles
5. Pick a bundle → notebook opens with your model context
6. Follow the steps, adapt to your data, get a customized model

### For Developers

See [Bundles Overview](#bundles-overview) to understand what each bundle does, then check individual bundle READMEs for technical details.

---

## Bundles Overview

### 1️⃣ **Fine-Tuning with PEFT (LoRA)**

**What:** Train only 1-10% of model parameters for quick adaptation.

**Real-world example:**
```
Base model: Llama-2-7B (general purpose)
Your task: Medical document summarization
↓
LoRA fine-tuning: Train 10M parameters (0.15%) on medical texts
↓
Result: Llama-2-7B specialized for medicine (in 2 hours, not 24)
```

**When to use:**
- ✅ Quick adaptation (2-4 GPU hours)
- ✅ Limited GPU memory (8-16GB fine)
- ✅ Want to ship tiny adapter files (50-200MB)
- ❌ Need maximum flexibility

**Tech stack:** PyTorch, PEFT, Hugging Face Transformers

**Path:** `customize-bundles/fine-tuning-peft/`

---

### 2️⃣ **Open Source Fine-Tuning (OSFT)**

**What:** Full model fine-tuning for maximum customization.

**Real-world example:**
```
Base model: Llama-2-7B
Your task: Company-specific business logic, new domain knowledge
↓
Full fine-tuning: Train all 7B parameters on your data
↓
Result: Llama-2-7B completely specialized (takes 24 hours, big costs)
```

**When to use:**
- ✅ Need maximum customization
- ✅ Large GPU cluster available (24-80GB memory)
- ✅ Have lots of training data (1000+)
- ❌ Limited budget (expensive)

**Tech stack:** PyTorch, Hugging Face Transformers, Kubeflow Trainer (optional)

**Path:** `customize-bundles/fine-tuning-osft/`

---

### 3️⃣ **Embedding Tuning for RAG**

**What:** Customize embeddings for your domain, improve document retrieval.

**Real-world example:**
```
You're building a customer support chatbot with RAG over internal docs:

1. User: "What's your refund policy?"
2. System embeds question
3. Retrieves similar docs (with generic embeddings: ~60% relevant)
4. LLM generates response (garbage in = garbage out)

After embedding tuning:
2. System embeds question
3. Retrieves similar docs (with domain embeddings: ~95% relevant)
4. LLM generates great response!
```

**When to use:**
- ✅ Building RAG systems
- ✅ Retrieval quality is poor with generic embeddings
- ✅ Have query-document pairs for your domain
- ✅ Want to train quickly (30 min!)
- ✅ Works on CPU

**Tech stack:** Sentence-Transformers, PyTorch

**Path:** `customize-bundles/embedding-tuning-rag/`

---

### 4️⃣ **Prompt Tuning and Experimentation**

**What:** Optimize prompts without any fine-tuning.

**Real-world example:**
```
You have GPT-4 API access. You want better responses:

v1: "Extract entities from: {text}"
    → 80% accuracy

v2: "You are an expert at entity extraction. Extract [PERSON], [ORG],
     [LOCATION] from: {text}. Be precise."
    → 92% accuracy

v3: "Extract entities. For each: 1) identify type, 2) verify context...
     {text}"
    → 89% accuracy

Winner: v2 (no fine-tuning, just better prompt!)
```

**When to use:**
- ✅ Have access to any LLM (API or local)
- ✅ Want quick improvements (hours)
- ✅ Small datasets (prompt engineering works)
- ✅ No GPU needed
- ✅ Want to avoid training time

**Tech stack:** Any LLM, Python, evaluation library

**Path:** `customize-bundles/prompt-tuning/`

---

### 5️⃣ **Evaluation with LLM-as-Judge**

**What:** Automatically score model outputs using another LLM.

**Real-world example:**
```
You fine-tuned a customer support model.
Old approach: Hire humans to grade 1000 responses (expensive, slow)

New approach: Use GPT-4 as grader
- Create rubric: "Rate helpfulness 1-5, accuracy 1-5, tone 1-5"
- Feed 1000 responses to GPT-4
- Get scores in 30 minutes
- Identify weak areas
- Retrain with more data on weak areas

Result: Continuous improvement without human labeling!
```

**When to use:**
- ✅ Need to evaluate many model outputs
- ✅ Human evaluation is too expensive
- ✅ Have a judge LLM available
- ✅ Can create good evaluation rubrics

**Tech stack:** Any LLM, evaluation framework, JSON processing

**Path:** `customize-bundles/evaluation/`

---

### 6️⃣ **Data Processing and Synthetic Data Generation**

**What:** Prepare training data and generate synthetic examples.

**Real-world example:**
```
You want to fine-tune on medical documents:

1. Cleaning: Remove duplicates, fix formatting, verify structure
2. Augmentation: For 100 examples, generate 500 variations
3. Synthetic generation: Use LLM to create realistic examples
4. Validation: Check data quality, balance classes

Result: High-quality training dataset ready for fine-tuning
```

**When to use:**
- ✅ Have messy data needing cleaning
- ✅ Have small dataset, need augmentation
- ✅ Need synthetic examples to augment data
- ✅ Want to validate data quality

**Tech stack:** Pandas, data processing libraries, LLMs for generation

**Path:** `customize-bundles/data-processing-sdg/`

---

## How Bundles Work Together

```
┌─────────────────────────────────────────────────┐
│  Model Catalog: User selects model & clicks    │
│  "Customize" → Workbench launches              │
└─────────────────────────┬───────────────────────┘
                          │
                          ↓
          ┌───────────────────────────────┐
          │  Jupyter Extension Offers:     │
          │  - Bundle selection menu       │
          │  - Model context passed        │
          └───────────────┬─────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
    ┌───────┐       ┌──────────┐      ┌─────────┐
    │ Data  │       │ LoRA or  │      │ Eval &  │
    │ Prep  │  →    │ Full FT  │  →   │ Monitor │
    └───────┘       └──────────┘      └─────────┘
        ↓                 ↓                 ↓
   Cleaned &        Trained Model      Quality
   Augmented        + Adapters          Metrics
    Data

Recommended workflow: Data Prep → Fine-tuning → Evaluation
```

## Bundle Structure

Each bundle follows this pattern:

```
customize-bundles/
├── README.md                          # Main overview (you are here)
├── registry.yaml                      # Machine-readable bundle index
│
├── fine-tuning-peft/
│   ├── notebook.ipynb                 # Main executable notebook
│   ├── metadata.yaml                  # Machine-readable config
│   ├── README.md                      # Detailed guide
│   └── data/
│       └── example_data.csv           # Sample data (optional)
│
├── embedding-tuning-rag/
│   ├── notebook.ipynb
│   ├── metadata.yaml
│   ├── README.md
│   └── data/
│       └── example_queries.csv
│
├── prompt-tuning/
│   ├── notebook.ipynb
│   ├── metadata.yaml
│   └── README.md
│
├── evaluation/
│   ├── notebook.ipynb
│   ├── metadata.yaml
│   └── README.md
│
├── data-processing-sdg/
│   ├── notebook.ipynb
│   ├── metadata.yaml
│   └── README.md
│
└── fine-tuning-osft/
    ├── notebook.ipynb
    ├── metadata.yaml
    └── README.md
```

## Key Assumptions All Bundles Make

Every bundle assumes:

1. **Model weights available** at `/mnt/models/`
   - Local path or HuggingFace model ID
   - Pre-downloaded before Workbench starts

2. **Data mounted** at `/mnt/datasets/`
   - Training data in CSV or JSON
   - Your responsibility to upload

3. **GPU access** (where needed)
   - LoRA and full fine-tuning: need GPU
   - Embeddings, prompt tuning, eval: CPU fine (but GPU faster)

4. **Output location** at `/mnt/outputs/`
   - All trained models, adapters, metrics go here
   - Persists across Workbench sessions via PVC

5. **Python libraries installed**
   - Provided by workbench image
   - See individual bundle README for requirements

## Using Bundles: Step-by-Step

### For a Complete Fine-Tuning Workflow

```bash
# Step 1: Prepare data
# - Gather your training examples
# - Format as CSV or JSON
# - Upload to /mnt/datasets/

# Step 2: Launch Workbench from Model Catalog
# - Select model: "meta-llama/Llama-2-7b"
# - Click "Customize"
# - Select workbench image: pytorch-cuda
# - Workbench boots with model pre-downloaded

# Step 3: Pick bundle in Jupyter extension
# - See menu: "What customization do you want?"
# - Select: "Fine-tuning with PEFT (LoRA)"
# - Notebook opens

# Step 4: Configure and run
# - Edit configuration cell (model path, data path, hyperparameters)
# - Run all cells sequentially
# - Monitor training loss

# Step 5: Deploy
# - Adapter saved to /mnt/outputs/adapter/
# - Download and integrate into your app
# - Use: model + adapter for inference
```

### For RAG Optimization

```bash
# Step 1: Prepare query-document pairs
# - Query: user question
# - Document: relevant text from your docs
# - Format: CSV with columns: query, positive_doc, negative_doc

# Step 2: Launch Workbench
# - Any model works (we're tuning embeddings, not the model)
# - Select: "datascience-cpu" or "pytorch-cuda"

# Step 3: Select "Embedding Tuning for RAG" bundle
# - Much lighter than LLM fine-tuning

# Step 4: Run notebook
# - Trains embedding model on your domain
# - Takes ~30 minutes

# Step 5: Deploy embeddings
# - Use custom embeddings in vector store
# - Retrieval quality improves significantly
```

## Creating Your Own Bundle

Want to add a new customization workflow? Follow these steps:

### 1. Create Directory
```bash
mkdir customize-bundles/your-workflow/
cd customize-bundles/your-workflow/
```

### 2. Write Notebook (`notebook.ipynb`)

Structure:
```
Cell 1: Markdown - Overview and goals
Cell 2: Code - ⚙️ Configuration section
         (Users modify this for their data)

Cells 3+: Code - Main implementation
          (Each with markdown explanation)

Last cell: Save outputs to /mnt/outputs/
```

Tips:
- Assume model at `/mnt/models/`
- Save outputs to `/mnt/outputs/`
- Use structured logging
- Include error handling
- Show sample outputs/metrics

### 3. Write Metadata (`metadata.yaml`)

```yaml
name: "Your Workflow Name"
version: "1.0.0"
category: "your-category"
difficulty: "beginner"  # or intermediate, advanced

requirements:
  gpu: false  # or true
  frameworks:
    - pytorch
    - other-lib

compatible_models:
  - type: "llm"
    examples: ["Llama-2", "Mistral"]

io_specification:
  inputs:
    training_data:
      description: "What format?"
      location: "/mnt/datasets/"
  outputs:
    model:
      description: "What you save"
      location: "/mnt/outputs/"

hyperparameters:
  param_name:
    description: "What it does"
    default: 0.001
    range: [0.0001, 0.01]

tags:
  - "tag1"
  - "tag2"
```

### 4. Write README (`README.md`)

Include:
- What the bundle teaches
- Prerequisites
- Key concepts explained
- Data format examples
- How to interpret results
- Troubleshooting
- Further reading

### 5. Add to Registry

Update `registry.yaml`:
```yaml
bundles:
  - id: "your-workflow"
    name: "Your Workflow Name"
    path: "your-workflow"
    description: "..."
    # ... rest of metadata
```

### 6. Test

Run through the notebook yourself:
- Does it work end-to-end?
- Are instructions clear?
- Does sample data work?
- Do outputs save correctly?

### 7. Document

Add to discovery sections in `registry.yaml`:
```yaml
discovery:
  by_use_case:
    "your-use-case": ["your-workflow"]
  by_difficulty:
    "beginner": ["your-workflow"]
```

---

## Integration with Model Catalog

How bundles connect to the Model Catalog (UI layer, not this repo):

1. **Customize Button**: UI shows "Customize" next to "Deploy"
2. **Model Context**: Passes model name, type, size to Workbench
3. **Jupyter Extension**: Discovers bundles from this repo
   - Filters by compatible model types
   - Filters by hardware available
   - Shows recommendations based on model
4. **Notebook Execution**: User runs notebook with model context

This repo provides **data** (bundles, metadata, notebooks).
The Model Catalog/Dashboard provides **UI** (button, discovery menu, routing).

---

## Recommended Workbench Images

| Bundle | Preferred | Alternatives | Why |
|--------|-----------|--------------|-----|
| LoRA Fine-tuning | pytorch-cuda | pytorch-rocm, datascience-cpu | Needs GPU + PyTorch |
| Full Fine-tuning | pytorch-cuda | pytorch-rocm | Needs GPU + PyTorch |
| Embedding Tuning | datascience-cpu | pytorch-cuda | CPU fine, lightweight |
| Prompt Tuning | minimal | datascience-cpu | No training needed |
| LLM-as-Judge | minimal | datascience-cpu | Just API calls |
| Data Processing | datascience-cpu | minimal | Pandas, notebooks |

---

## File Structure in This Repo

```
notebooks/
├── README.md                          # Main project README
├── CUSTOMIZE.md                       # This file
├── customize-bundles/                 # All customization bundles
│   ├── README.md                      # Overview (what bundles are)
│   ├── registry.yaml                  # Machine-readable index
│   │
│   ├── fine-tuning-peft/
│   ├── fine-tuning-osft/
│   ├── embedding-tuning-rag/
│   ├── prompt-tuning/
│   ├── evaluation/
│   └── data-processing-sdg/
│       (each with: notebook.ipynb, metadata.yaml, README.md)
│
├── jupyter/                           # Workbench images (existing)
├── codeserver/                        # Code Server image (existing)
├── rstudio/                           # RStudio image (existing)
└── ...
```

---

## Support & Contribution

### Finding Help

1. **Bundle not working?** Check individual bundle README
2. **Need different workflow?** Create a new bundle (see "Creating Your Own Bundle")
3. **Found a bug?** Open issue on GitHub
4. **Have feedback?** See [CONTRIBUTING.md](CONTRIBUTING.md)

### Contributing a Bundle

1. Fork repository
2. Create new bundle following the structure
3. Test thoroughly
4. Submit PR with documentation
5. Maintainers review and merge

---

## FAQ

**Q: Do I need GPU for all bundles?**
A: No. Embedding tuning, prompt tuning, evaluation, and data processing work on CPU (slow but fine). Only LoRA and full fine-tuning strongly benefit from GPU.

**Q: Can I use these bundles without Model Catalog?**
A: Yes! Notebooks work standalone. Just:
   1. Download notebook.ipynb
   2. Place model at `/mnt/models/`
   3. Place data at `/mnt/datasets/`
   4. Run in any Jupyter environment

**Q: How do I combine multiple bundles?**
A: See "Recommended Workflow Chains" in `registry.yaml`. Example: Data Prep → LoRA FT → Evaluation

**Q: Can I modify the notebooks?**
A: Absolutely! They're templates. Customize hyperparameters, architecture, evaluation metrics for your use case.

**Q: How large can training datasets be?**
A: Tested up to 100k examples. Larger datasets work but may need distributed training (see OSFT bundle for Kubeflow Trainer integration).

**Q: What if my model isn't on HuggingFace?**
A: Place it locally at `/mnt/models/` and reference the path in notebooks. Works with any model format PyTorch understands.

---

## Glossary

| Term | Definition |
|------|-----------|
| **LoRA** | Low-Rank Adaptation: training small adapters instead of full model |
| **PEFT** | Parameter-Efficient Fine-Tuning: any method that trains <10% params |
| **OSFT** | Open Source Fine-Tuning: full model training |
| **RAG** | Retrieval-Augmented Generation: finding docs then generating answer |
| **Bundle** | Self-contained notebook + metadata for one customization workflow |
| **Adapter** | Small weights trained via LoRA, applied on top of base model |
| **Embedding** | Converting text to vectors/numbers for similarity search |
| **Prompt Tuning** | Optimizing text instructions without model training |
| **LLM-as-Judge** | Using an LLM to evaluate outputs of another LLM |

---

**Last updated:** 2024-04-09
**Maintained by:** OpenDataHub Community
