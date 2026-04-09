# Customize Bundles for Model Customization

Welcome to the Customize Bundles! These are curated, runnable examples that help you adapt AI models to your specific needs. Instead of discovering and cloning notebooks manually, you get a "one-click" entry point from the Model Catalog directly into a working example.

## What Are Customization Bundles?

A **customization bundle** is a self-contained, runnable Jupyter notebook with:

- **A working example** that you can run immediately (no setup required beyond model weights)
- **Clear assumptions** about what's already available (GPU, libraries, model location)
- **Step-by-step guidance** through the customization process
- **Well-documented code** so you understand what's happening and can adapt it

Think of it like a **recipe for adapting an AI model** — instead of starting from scratch, you follow a proven pattern and swap in your own data or configuration.

## Bundle Types (What Each Does)

### 1. **Fine-Tuning: Open Source Fine-Tuning (OSFT)**

**What is it?**
- Trains an entire model (or a large portion of it) on your data
- Works with models that support open-source fine-tuning frameworks
- Produces a new model variant optimized for your task

**Real-world example:**
- You have a general-purpose LLM (like Llama 2 or Mistral)
- You want it specialized for medical document summarization
- OSFT: Train on 1,000 medical documents → get a model that understands medical terminology

**Key characteristics:**
- ✅ Most flexible — can deeply customize model behavior
- ❌ Requires more compute (trains many/all parameters)
- ❌ Needs more training data (typically 100s-1000s of examples)
- **Use when:** You need significant behavioral changes or domain specialization

**Tools used:**
- Hugging Face Transformers for PyTorch/TensorFlow
- Kubeflow Trainer for distributed training on Kubernetes

---

### 2. **Fine-Tuning: Parameter-Efficient Fine-Tuning (PEFT)**

**What is it?**
- Trains only a **small subset of model parameters** (1-10% instead of 100%)
- Freezes the main model and adds trainable "adapter" layers
- Much faster and cheaper than full fine-tuning

**Real-world example:**
- You have a pre-trained language model (Llama 2)
- You want it adapted for customer support conversations
- PEFT (LoRA/QLoRA): Train only 2 million adapter parameters instead of 7 billion
- Result: Takes 1/10th the time, 1/10th the GPU memory, same quality customization

**Common PEFT techniques:**
- **LoRA** (Low-Rank Adaptation) — adds small trainable matrices to each layer
- **QLoRA** — combines LoRA with 4-bit quantization (even cheaper)
- **Prefix Tuning** — adds learnable "prefix" tokens
- **Adapters** — inserts small neural networks between layers

**Key characteristics:**
- ✅ Fast (5-10x faster than full fine-tuning)
- ✅ GPU-efficient (fits on consumer GPUs)
- ✅ Cheap (fewer compute hours)
- ✅ Portable (adapters are tiny files, easy to ship)
- ❌ Less flexible than full fine-tuning (can't change everything)
- **Use when:** You want to adapt a model quickly without massive compute budgets

**Tools used:**
- PEFT library (Meta's parameter-efficient fine-tuning)
- LoRA implementation
- QLoRA for quantized training

---

### 3. **Embedding Tuning for RAG (Retrieval-Augmented Generation)**

**What is it?**
- Customizes embedding models (the part that converts text → numbers)
- Improves relevance of retrieved documents in RAG pipelines
- Much simpler than fine-tuning LLMs

**Real-world example:**
- You're building a chatbot over your company's internal documents
- You use a RAG pipeline: user question → embed question → find similar docs → give docs to LLM
- **Problem:** Generic embeddings don't understand your company's jargon
- **Solution:** Embed tuning — train the embedding model on your domain (contracts, policies, FAQs)
- Result: Retrieval improves from 60% relevant documents → 95% relevant documents

**Key characteristics:**
- ✅ Much simpler than LLM fine-tuning
- ✅ Requires less data (50-500 examples often sufficient)
- ✅ Very fast to train (minutes to hours)
- ✅ Huge impact on RAG quality
- ❌ Only improves retrieval, not generation
- **Use when:** You're building RAG systems and want better document retrieval

**Training data format:**
- Query-Document pairs with relevance labels
- Example: ("refund policy for electronics", "doc_12345.pdf", relevance=high)

**Tools used:**
- Sentence-Transformers library
- Triplet loss or contrastive loss functions
- Cross-encoder models for re-ranking

---

### 4. **Prompt Tuning and Experimentation**

**What is it?**
- Finds the best **prompts** (text instructions) for your task without fine-tuning
- Explores different prompt formats, examples, and instructions
- Works with any model via API

**Real-world example:**
- You have access to GPT-4 or Llama via API
- You want it to extract entities from customer emails
- **Prompt tuning:** Test 10 different prompts and prompt structures
  - v1: "Extract person names from: {email}"
  - v2: "You are an entity extraction expert. Extract all entities: {email}"
  - v3: "Extract: [PERSON], [ORG], [LOCATION] from: {email}"
- Pick the one with best accuracy
- Result: 89% → 94% accuracy without any model training

**Why it matters:**
- ✅ Works with any model (no fine-tuning required)
- ✅ Free or cheap (only API calls)
- ✅ Fast (test in hours)
- ✅ Great for small datasets
- ❌ Limited by model capabilities (can't teach new skills)
- **Use when:** You want quick wins without training time

**Techniques explored:**
- Few-shot prompting (providing examples)
- Chain-of-Thought (asking model to explain reasoning)
- Structured output formats (JSON, XML, etc.)
- System prompts vs user prompts

---

### 5. **Evaluation: LLM-as-Judge**

**What is it?**
- Uses an LLM to evaluate outputs of another LLM
- Grades model behavior without manual human labeling
- Automates quality assessment

**Real-world example:**
- You fine-tuned a model for customer support responses
- You want to measure quality: Are responses helpful? Accurate? Polite?
- **Traditional approach:** Hire humans to grade 1,000 responses (expensive, slow)
- **LLM-as-Judge:** Use GPT-4 to grade responses automatically
  - Create a scoring rubric (helpfulness: 1-5, accuracy: 1-5, tone: 1-5)
  - Run your model's responses through the grader
  - Get scores in seconds for thousands of responses
- Result: Continuous feedback loop for model improvement

**Scoring approaches:**
- **Binary:** Is this response good? (Yes/No)
- **Rating scale:** Score 1-5
- **Rubric-based:** Grade across multiple dimensions
- **Comparison:** Is response A better than response B?

**Key characteristics:**
- ✅ Automates evaluation (no manual labeling)
- ✅ Scales to thousands of examples
- ✅ Provides detailed feedback
- ❌ Requires careful prompt design (grader bias)
- ❌ Only as good as the judge model
- **Use when:** You need continuous evaluation without human labeling

**Tools used:**
- Judge LLM (GPT-4, Llama, Claude, etc.)
- Structured evaluation prompts
- Scoring aggregation and analysis

---

## How These Bundles Work Together

```
1. Start: You picked a model in Model Catalog → click "Customize"
                           ↓
2. Workbench: Preconfigured environment launches (GPU, libraries, model weights)
                           ↓
3. Bundle: Jupyter extension offers you these customization options:

   ┌─ Want domain specialization?     → OSFT (full fine-tuning)
   ├─ Want quick adaptation?           → PEFT (parameter-efficient)
   ├─ Building a RAG system?           → Embedding tuning
   ├─ Want to optimize without training? → Prompt tuning
   └─ Need to evaluate quality?         → LLM-as-Judge evaluation
                           ↓
4. Execute: You run the notebook, adapt to your data, get customized model
                           ↓
5. Deploy: Use the customized model in your application
```

## Bundle Structure

Each bundle follows this structure:

```
{bundle-name}/
├── notebook.ipynb          # Main runnable notebook
├── metadata.yaml           # Machine-readable bundle info
├── README.md              # Usage guide and assumptions
└── data/
    └── example_data.csv   # Optional: sample data for testing
```

### Metadata Fields (metadata.yaml)

```yaml
name: "Fine-Tuning with PEFT"
version: "1.0"
description: "Parameter-Efficient Fine-Tuning using LoRA"

# What hardware/software is needed
requirements:
  gpu: true
  gpu_type: cuda  # cuda, rocm, or cpu
  memory_gb: 16
  frameworks:
    - pytorch>=2.0
    - peft>=0.4.0

# What model types this works for
compatible_models:
  - type: "llm"           # LLM, embedding, etc.
    architectures: ["transformer-based"]
    min_params: "1B"      # Minimum model size

# Recommended workbench image
workbench_image:
  name: "pytorch-cuda"
  min_python_version: "3.10"

# Inputs and outputs
inputs:
  training_data: "CSV file with 'text' and 'label' columns"
  model_path: "/mnt/models/base-model"
outputs:
  adapter_weights: "/mnt/outputs/adapter"
  metrics: "/mnt/outputs/metrics.json"

# Estimated runtime and cost
complexity:
  estimated_time_minutes: 120
  gpu_hours_needed: 4
```

## Assumptions All Bundles Make

Every bundle assumes:

1. **Model weights are available** at a known path (`/mnt/models/base-model` by default)
2. **GPU access** (where needed — CPU bundles can train on CPU too)
3. **Persistent volume** for inputs, outputs, and intermediate files
4. **Required Python libraries** installed in the workbench image
5. **Standard file paths:**
   - Training data: wherever you mount it
   - Model location: `/mnt/models/`
   - Outputs: `/mnt/outputs/`

## Getting Started

Pick a bundle based on your use case:

```bash
# 1. Launch workbench with your model
# (from Model Catalog: click "Customize")

# 2. Jupyter extension loads available bundles
# and displays your options

# 3. Select bundle → notebook opens in Jupyter

# 4. Run cells sequentially, customize parameters at top of notebook

# 5. Trained model/adapter/evaluation results in /mnt/outputs/
```

## Adding Your Own Bundle

If you want to create a new customization workflow:

1. Create folder: `customize-bundles/your-workflow/`
2. Create `notebook.ipynb` with clear structure:
   - Cell 1: Configuration (model path, data path, hyperparameters)
   - Cells 2-N: Implementation with markdown explanations
   - Last cell: Save outputs to `/mnt/outputs/`
3. Write `metadata.yaml` with requirements
4. Write `README.md` with assumptions and guidance
5. Add to `registry.yaml` (see below)

## Bundle Registry

See `registry.yaml` for machine-readable index of all bundles, used by:
- Jupyter extension to discover bundles
- Model Catalog to recommend bundles for each model type
- Documentation to list available options

---

**Questions or issues?**
- Check individual bundle READMEs for detailed guidance
- See the [parent README](../README.md) for project overview
