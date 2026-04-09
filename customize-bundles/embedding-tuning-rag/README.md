# Embedding Tuning for RAG

## What Will You Learn?

This notebook teaches you how to:
- ✅ Load a pre-trained embedding model
- ✅ Customize embeddings for your specific domain
- ✅ Improve retrieval quality in RAG pipelines
- ✅ Evaluate embedding quality
- ✅ Deploy custom embeddings

## Before You Start

### Prerequisites

**What you need:**
- [ ] Base embedding model (from Sentence-Transformers)
- [ ] Training data: query-document pairs with relevance labels
- [ ] At least 4GB GPU memory (or CPU is fine)

**What you should know:**
- How RAG systems work (retrieval + generation)
- What embeddings are (text → numbers)
- Basic Python knowledge

### Recommended Workbench Image

```bash
datascience-cpu:latest  # CPU is actually fine for embeddings!
# OR
pytorch-cuda:latest     # If you want GPU speed
```

## What is Embedding Tuning? (Quick Explanation)

**Before Tuning:**
```
Generic embedding model trained on Wikipedia/Common Crawl
User: "refund policy"
↓
Finds documents about: money, returns, products
(Not specific to YOUR domain)
```

**After Tuning:**
```
Embedding model trained on YOUR domain data
User: "refund policy"
↓
Finds documents about: company refunds, customer service, policies
(Exactly what you need!)
```

## Why This Matters for RAG

RAG works in steps:
1. **Embed** the user question
2. **Retrieve** similar documents
3. **Generate** answer using those documents

**Problem:** If retrieval is bad (step 2), generation fails no matter how good your LLM is.

**Solution:** Tune embeddings for YOUR domain → better retrieval → better answers!

## Data Format

### CSV Format (Simplest)

```csv
query,positive_doc,negative_doc
"what is return policy","Returns within 30 days allowed","Shipping takes 5-7 days"
"how to track order","Order tracking page here","Login with email"
```

Or with relevance scores:

```csv
query,document,relevance
"refund policy","We accept returns within 30 days",1.0
"return policy","Shipping takes 5-7 business days",0.1
```

### JSON Format

```json
[
  {
    "query": "what is return policy",
    "positive_doc": "Returns within 30 days allowed",
    "negative_doc": "Shipping takes 5-7 days"
  }
]
```

## Key Concepts

### Triplet Loss (What We Use)

The model learns:
- Query and positive document should have **similar embeddings** (close together)
- Query and negative document should have **different embeddings** (far apart)

```
    Positive doc ← close to
            ↑
         Query (anchor)
            ↓
    Negative doc ← far from
```

This naturally adapts embeddings to your domain.

### Training Data Quality

**Good triplets:**
- Query: "How do I refund?"
- Positive: "Refund policy: items within 30 days..."
- Negative: "Shipping takes 5-7 business days"

**Bad triplets:**
- Query: "Hello"
- Positive: "Hi there"
- Negative: "Goodbye"
(Too simple, doesn't help much)

## How This Notebook Works

```
Step 1: Load base model
  ↓
Step 2: Load training data (query-doc pairs)
  ↓
Step 3: Create triplet dataset
  ↓
Step 4: Train with triplet loss
  ↓
Step 5: Evaluate on validation set
  ↓
Step 6: Save custom embeddings
  ↓
Step 7: Ready to use in RAG!
```

## Expected Runtime and Resources

| Metric | Value |
|--------|-------|
| Training time | 10-60 minutes |
| GPU memory needed | 4-8 GB (or CPU) |
| Data size | 10-1000 training pairs |
| Output size | ~100-500 MB |

## Key Hyperparameters

**Learning Rate** (default: 2e-5)
- How fast the model learns
- Lower = slower but more stable
- Higher = faster but can miss good solution

**Batch Size** (default: 16)
- Number of triplets per update
- Larger = faster but needs more memory
- Smaller = slower but works on weak GPUs

**Epochs** (default: 2-3)
- How many times to see all data
- Usually 2-3 is enough for embeddings

## Outputs You'll Get

### 1. Fine-tuned Model
```
/mnt/outputs/embedding-model/
├── config.json
├── model.safetensors  # Your custom weights
├── sentence_bert_config.json
└── tokenizer_config.json
```

### 2. Evaluation Metrics
```json
{
  "mean_average_precision": 0.92,
  "retrieval_accuracy_top_1": 0.88,
  "retrieval_accuracy_top_5": 0.96,
  "training_time_minutes": 15
}
```

## Using Your Custom Embeddings in RAG

### Option 1: With LangChain
```python
from sentence_transformers import SentenceTransformer
from langchain.embeddings import HuggingFaceEmbeddings

# Load your tuned embeddings
embeddings = HuggingFaceEmbeddings(
    model_name="/mnt/outputs/embedding-model"
)

# Use in vector store
vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embeddings
)
```

### Option 2: Direct Usage
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("/mnt/outputs/embedding-model")

# Embed your documents
doc_embeddings = model.encode(documents)

# Embed queries
query_embedding = model.encode(user_query)

# Find similar documents
similarities = cosine_similarity([query_embedding], doc_embeddings)
```

## Troubleshooting

### Low Retrieval Accuracy
```
Solution 1: Add more training data (more domain examples)
Solution 2: Train longer (increase num_epochs)
Solution 3: Improve triplet quality (make negatives harder)
Solution 4: Increase learning rate if loss is stable
```

### Training Loss Doesn't Decrease
```
Solution 1: Lower learning rate (try 1e-5)
Solution 2: Check data format (should be valid pairs)
Solution 3: Increase batch size (more examples per step)
Solution 4: Make sure you have GPU/compute available
```

### Memory Error
```
Solution 1: Reduce batch_size (16 → 8)
Solution 2: Use CPU instead (slower but works)
Solution 3: Use smaller base model (all-MiniLM-L6-v2)
```

## When to Use This Bundle

✅ **Use when:**
- Building RAG over your documents
- Standard embeddings don't understand your domain
- You have 10+ labeled query-document pairs
- You want to improve retrieval quality

❌ **Don't use when:**
- You don't have training data
- Standard embeddings work well enough
- You need LLM fine-tuning (use PEFT bundle instead)

## Next Steps

1. ✅ Run this notebook with your domain data
2. ✅ Evaluate retrieval quality
3. ✅ Deploy custom embeddings in your RAG system
4. ✅ Monitor retrieval metrics in production
5. ✅ Add more data and retrain if needed

## Further Reading

- [Sentence-Transformers Documentation](https://www.sbert.net/)
- [Fine-tuning Guide](https://www.sbert.net/docs/training/overview.html)
- [RAG Best Practices](https://python.langchain.com/docs/modules/data_connection/)
- [Triplet Loss Explained](https://arxiv.org/abs/1503.03832)

---

**Ready?** Open `notebook.ipynb` and start tuning! 🎯
