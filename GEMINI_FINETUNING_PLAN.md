# Gemini Fine-Tuning Implementation Plan

## Current State
- Using **few-shot prompting** (in-context learning) in `src/model/model_finetune.py`
- Selects 8 diverse examples, embeds them in system prompt
- No actual parameter tuning; model is base Gemini

## Goal
Implement **actual parameter tuning** via Gemini's fine-tune API for better domain-specific performance.

## Implementation Steps

### 1. Convert Training Data to JSONL
Source: `src/data/processed/conversation_training_data.json` (41 examples)

Format required:
```json
{"text_input": "I'm struggling with credit card debt", "output": "I can hear how much of a burden this is..."}
```

### 2. Call Gemini Fine-Tune API
```python
import google.generativeai as genai

operation = genai.create_fine_tuned_model(
    display_name="financial-therapist-v1",
    source_model="models/gemini-1.5-flash-001",  # or gemini-1.5-pro
    training_data=[training_file],
    epoch_count=3,
    batch_size=4,
    learning_rate=0.001
)

# Wait for completion (hours to days)
result = operation.result()
fine_tuned_model = result.name  # e.g., tunedModels/financial-therapist-v1
```

### 3. Use Fine-Tuned Model
Replace model calls in `src/inference/predictor.py` and `src/model/model_train.py`:
```python
response = client.models.generate_content(
    model="tunedModels/financial-therapist-v1",
    contents=user_query
)
```

## Trade-Offs
| Aspect | Few-Shot | Parameter Tuning |
|--------|----------|------------------|
| Cost | Free | $1-3+ per run |
| Time | Instant | 4-48 hours |
| Quality | Good | Excellent |
| Setup | Simple | Requires JSONL + API call |

## Resource Requirements
- Budget: ~$2-5 per fine-tune run
- Time: 4-48 hours for training
- Data: 41 conversation examples (minimum ~10-20 needed)

## Files to Modify
- `src/model/model_finetune.py` — refactor to JSONL conversion + API call
- `src/inference/predictor.py` — update model name to fine-tuned variant
- `src/model/model_train.py` — update model reference if testing different versions

## Status
Saved for later implementation when budget allows.
