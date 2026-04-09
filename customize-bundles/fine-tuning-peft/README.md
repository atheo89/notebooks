# Fine-Tuning with PEFT (LoRA)

## What Will You Learn?

This notebook teaches you how to:
- ✅ Load a pre-trained LLM efficiently
- ✅ Apply LoRA (Low-Rank Adaptation) to make it trainable with small GPUs
- ✅ Fine-tune the model on your custom dataset
- ✅ Evaluate performance and save the trained adapter
- ✅ Deploy the adapter alongside the base model

## Before You Start

### Prerequisites

**What you need:**
- [ ] A pre-trained model (HuggingFace model ID or local path at `/mnt/models/`)
- [ ] Training data as CSV or JSON file
- [ ] At least 8GB GPU memory (16GB recommended)
- [ ] PyTorch and PEFT libraries installed (provided in workbench)

**What you should know:**
- Basic Python and PyTorch concepts
- What fine-tuning is (adapting a model to your data)
- What LoRA is (efficient parameter adaptation)

### Recommended Workbench Image

```bash
pytorch-cuda:latest  # NVIDIA GPU support
# OR
pytorch-rocm:latest  # AMD GPU support
```

## What is LoRA? (Quick Explanation)

**Regular Fine-Tuning:**
```
Model has 7 billion parameters
Train all 7 billion
💾 7B weights saved
⏱️ Takes 24 hours
💰 Expensive
```

**LoRA Fine-Tuning:**
```
Model has 7 billion parameters
Train only 10 million adapter weights (0.15%)
💾 10M weights saved (1000x smaller!)
⏱️ Takes 2-3 hours
💰 1/10th the cost
```

It works because research shows you don't need to update all parameters to adapt a model—you can achieve similar results by training small, specially-placed "adapters."

## Data Format

### CSV Format (Simplest)

```csv
text,label
"What is AI?","AI is artificial intelligence..."
"Explain ML","Machine learning is..."
```

Or with instructions (for instruction-following models):

```csv
instruction,input,output
"Summarize","This is a long text...","Summary: ..."
"Classify","email text","spam/ham"
```

### JSON Format (Alternative)

```json
[
  {
    "text": "What is AI?",
    "label": "AI is artificial intelligence..."
  },
  {
    "text": "Explain ML",
    "label": "Machine learning is..."
  }
]
```

## Key Concepts in This Notebook

### LoRA Parameters

- **`r` (rank)**: Size of adapter matrices. Higher = more capacity but slower.
  - Common values: 8, 16, 32
  - Start with 8, increase if model underfits

- **`lora_alpha`**: Scaling factor. Usually 2x the rank.
  - If r=8, set alpha=16

- **`target_modules`**: Which layers to add LoRA to
  - Common: `["q_proj", "v_proj"]` (query and value projections in attention)
  - You can add more modules if needed

### Training Hyperparameters

- **`learning_rate`**: How fast the model learns
  - Typical: 3e-4 (0.0003) for LoRA
  - Try 1e-4 if loss doesn't decrease, 5e-4 if it's noisy

- **`batch_size`**: Examples per training step
  - Larger = faster training but needs more memory
  - Common: 8-16 with LoRA

- **`num_epochs`**: How many times to see all training data
  - Usually 2-5 for fine-tuning

## How This Notebook Works

```
Step 1: Setup
├─ Import libraries
├─ Load base model from /mnt/models/
└─ Load training data from /mnt/datasets/

Step 2: Configure LoRA
├─ Define LoRA parameters (r, alpha, target_modules)
├─ Apply LoRA to model
└─ Check that only 0.1-1% parameters are trainable

Step 3: Training
├─ Create data loaders
├─ Set up optimizer and learning rate scheduler
├─ Run training loop (multiple epochs)
├─ Track loss and metrics

Step 4: Evaluation
├─ Run on validation set
├─ Compute accuracy/perplexity
└─ Display results

Step 5: Save
├─ Save adapter weights to /mnt/outputs/adapter/
├─ Export metrics and logs
└─ Ready to deploy!
```

## Expected Runtime and Resources

| Metric | Value |
|--------|-------|
| Estimated time | 30-120 minutes (depending on data size) |
| GPU memory needed | 8-16 GB |
| Data size | 50-5000 training examples |
| Output size | ~50-200 MB (adapter weights) |

## Outputs You'll Get

### 1. Adapter Weights
```
/mnt/outputs/adapter/
├── adapter_config.json      # LoRA configuration
├── adapter_model.safetensors # Trained weights
└── README.md                # How to use
```

### 2. Metrics
```json
{
  "final_loss": 0.45,
  "val_accuracy": 0.92,
  "training_time_hours": 2.5,
  "total_params": 7000000000,
  "trainable_params": 10000000
}
```

### 3. Training Logs
```
Epoch 1/3: Loss = 2.34, Val Acc = 0.78
Epoch 2/3: Loss = 1.12, Val Acc = 0.85
Epoch 3/3: Loss = 0.45, Val Acc = 0.92
```

## How to Use Your Trained Model

### Option 1: In Python (Local)
```python
from peft import PeftModel
from transformers import AutoModelForCausalLM

# Load base model
base_model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-2-7b-hf")

# Load your adapter
model = PeftModel.from_pretrained(base_model, "/mnt/outputs/adapter")

# Use it
output = model.generate(input_ids, max_length=200)
```

### Option 2: Deploy in Production
```bash
# Copy to your application
cp -r /mnt/outputs/adapter /your/deployment/path/

# Your app loads it
model = PeftModel.from_pretrained(base_model, "/your/deployment/path/")
```

## Troubleshooting

### "Out of Memory" Error
```
Solution 1: Reduce batch_size (8 → 4)
Solution 2: Use gradient_accumulation_steps
Solution 3: Use QLoRA (4-bit quantization)
```

### Training Loss Isn't Decreasing
```
Solution 1: Increase learning_rate (try 5e-4)
Solution 2: Increase r (8 → 16)
Solution 3: Check data quality (duplicates, noise)
Solution 4: Train longer (increase num_epochs)
```

### Validation Accuracy Low
```
Solution 1: Add more training data
Solution 2: Train longer (more epochs)
Solution 3: Increase r (bigger adapters)
Solution 4: Lower learning rate for finer tuning
```

## Next Steps

1. ✅ Run this notebook with your data
2. ✅ Evaluate the adapter quality
3. ✅ Deploy the adapter in your application
4. ✅ Iterate: if results aren't good enough, try:
   - More training data
   - Longer training (more epochs)
   - Larger adapters (higher r)
   - Full fine-tuning (if budget allows)

## Further Reading

- [PEFT Documentation](https://huggingface.co/docs/peft/)
- [LoRA Paper](https://arxiv.org/abs/2106.09685)
- [Hugging Face Fine-tuning Guide](https://huggingface.co/docs/transformers/training)
- [Parameter-Efficient Transfer Learning](https://arxiv.org/abs/2203.06904)

---

**Ready?** Open `notebook.ipynb` and start training! 🚀
