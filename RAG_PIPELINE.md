# RAG Pipeline: Complete Implementation Guide

## Overview

This document describes the complete Retrieval-Augmented Generation (RAG) pipeline implementation for the Financial Therapist Chatbot.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAG PIPELINE WORKFLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: RAW DATA (S3 Upload)                                  │
│  ├─ conversations.json  → Upload to S3                         │
│  ├─ FAQs_raw.json      → s3://f2-fintech-kb/raw/              │
│  ├─ scenarios_raw.json                                         │
│  └─ system_prompt_raw.md                                       │
│           ↓                                                    │
│  Step 2: DOWNLOAD FROM S3                                      │
│  └─ Download processed files from S3                           │
│           ↓                                                    │
│  Step 3: DATA PROCESSING                                       │
│  ├─ Process FAQs          → faqs.json                          │
│  ├─ Process Scenarios     → scenarios.json                     │
│  └─ Process System Prompt → system_prompt.md                   │
│           ↓                                                    │
│  Step 4: EMBEDDING GENERATION                                  │
│  └─ Use Gemini text-embedding-2 (768 dimensions)              │
│           ↓                                                    │
│  Step 5: VECTOR DATABASE (Pinecone)                            │
│  ├─ Index Name: f2-therapy-index                              │
│  ├─ Dimension: 768                                             │
│  ├─ Metric: cosine                                             │
│  └─ Load FAQs, Scenarios, System Prompt                        │
│           ↓                                                    │
│  Step 6: MODEL TRAINING                                        │
│  ├─ Model: Gemini 3.1 Flash                                   │
│  ├─ System Prompt: Load from processed data                   │
│  └─ Training Data: Conversation examples                       │
│           ↓                                                    │
│  Step 7: CHATBOT TESTING                                       │
│  └─ Test RAG pipeline with sample queries                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Components

### 1. S3 Storage Manager (`src/knowledge/s3_storage.py`)
- Uploads raw knowledge base files to AWS S3
- Downloads files from S3 to local system
- Manages S3 bucket connection and file sync

**Key Methods:**
- `upload_file()`: Upload single file
- `download_file()`: Download single file
- `sync_raw_to_s3()`: Sync all raw files
- `sync_processed_to_s3()`: Sync processed files

### 2. Data Processor (`src/knowledge/data_processor.py`)
- Processes raw JSON files into formatted documents
- Extracts and processes system prompt
- Adds metadata and keywords

**Key Methods:**
- `process_scenarios()`: Format scenarios with metadata
- `process_faqs()`: Format FAQs with categories
- `process_system_prompt()`: Clean and format system prompt
- `process_all()`: Run all processing steps

### 3. Embedder (`src/knowledge/embedder.py`)
- Generates embeddings using Google Gemini
- Uses text-embedding-2 model (768 dimensions)
- Converts text to vector representations

**Key Methods:**
- `get_embeddings()`: Initialize embedding model
- `embed_text()`: Convert text to embedding vector

### 4. Knowledge Loader (`src/knowledge/loader.py`)
- Loads processed documents into Pinecone vector DB
- Creates vector records with metadata
- Manages index operations

**Key Methods:**
- `load_scenarios()`: Load scenario embeddings
- `load_faqs()`: Load FAQ embeddings
- `load_all()`: Load all documents

### 5. Knowledge Retriever (`src/knowledge/retriever.py`)
- Retrieves relevant documents from Pinecone
- Performs similarity search
- Returns context for RAG

**Key Methods:**
- `retrieve()`: Get top-k similar documents
- `get_context()`: Get formatted context

### 6. Model Trainer (`src/model/model_train.py`)
- Trains model using Gemini 3.1 Flash preview
- Prepares training data from conversations
- Validates model functionality

**Key Methods:**
- `prepare_training_data()`: Extract training examples
- `load_system_prompt()`: Load system prompt
- `train()`: Run training process
- `test_model_response()`: Validate model

### 7. Therapy Chatbot (`src/inference/predictor.py`)
- RAG-enabled chatbot using Gemini + Pinecone
- Retrieves context from vector DB
- Generates empathetic responses

**Key Methods:**
- `chat(user_message, use_rag=True)`: Main chat method
- `_get_relevant_context()`: Retrieve KB context
- `_build_rag_prompt()`: Build enhanced prompt

### 8. RAG Pipeline Orchestrator (`src/rag_pipeline.py`)
- Orchestrates entire pipeline
- Runs all 7 steps in sequence
- Provides progress tracking and summary

## Environment Setup

### Required Environment Variables

Create a `.env` file in the project root:

```bash
# Google API Configuration
GEMINI_API_KEY="your-gemini-api-key"

# Pinecone Configuration
PINECONE_API_KEY="your-pinecone-api-key"

# AWS S3 Configuration
AWS_ACCESS_KEY_ID="your-aws-key"
AWS_SECRET_ACCESS_KEY="your-aws-secret"
AWS_REGION="us-east-1"
S3_BUCKET_NAME="f2-fintech-kb"

# Database Configuration
DATABASE_URL="postgresql://user:password@localhost:5432/f2_therapist"
```

### Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
pip install google-generativeai
```

2. **Ensure data files exist:**
```
src/data/raw/
├── conversations.json
├── FAQs_raw.json
├── scenarios_raw.json
└── system_prompt_raw.md
```

## Running the RAG Pipeline

### Option 1: Run Complete Pipeline

```bash
cd src
python rag_pipeline.py
```

This will execute all 7 steps:
1. Upload to S3
2. Download from S3
3. Process data
4. Generate embeddings
5. Load to Pinecone
6. Train model
7. Test chatbot

### Option 2: Run with S3 Skip (for local testing)

```bash
python rag_pipeline.py --skip-s3-upload --skip-s3-download
```

### Option 3: Test Individual Components

```bash
# Test data processing
python -c "from knowledge.data_processor import DataProcessor; DataProcessor().process_all()"

# Test embeddings
python -c "from knowledge.embedder import embed_text; print(embed_text('test'))"

# Test Pinecone loading
python -c "from knowledge.loader import KnowledgeLoader; KnowledgeLoader().load_all()"

# Test model training
python src/model/model_train.py

# Test chatbot
python src/inference/predictor.py
```

## Data Flow

### Raw Data Structure

**FAQs_raw.json:**
```json
[
  {
    "id": "faq_001",
    "question": "How do I understand my credit card statement?",
    "answer": "Your credit card statement shows...",
    "metadata": {
      "category": "Credit Cards",
      "source": "General Banking"
    }
  }
]
```

**scenarios_raw.json:**
```json
[
  {
    "id": "scenario_001",
    "title": "Low Income, High Debt",
    "content": "A person having low income...",
    "category": "Debt Management",
    "severity": "high"
  }
]
```

**system_prompt_raw.md:**
```
You are a compassionate Financial Therapist...
[System instructions and personality definition]
```

### Processed Data Structure

**faqs.json:**
```json
[
  {
    "id": "faq_001",
    "question": "How do I understand my credit card statement?",
    "answer": "Your credit card statement shows...",
    "category": "Credit Cards",
    "tags": ["credit_card", "statement", "basics"],
    "processed_at": "2026-04-25T10:30:00.000Z"
  }
]
```

**scenarios.json:**
```json
[
  {
    "id": "scenario_001",
    "title": "Low Income, High Debt",
    "content": "A person having low income...",
    "category": "Debt Management",
    "severity": "high",
    "keywords": ["debt", "income", "management", "planning"],
    "processed_at": "2026-04-25T10:30:00.000Z"
  }
]
```

### Pinecone Index Structure

**Index Configuration:**
- Name: `f2-therapy-index`
- Dimension: 768 (matches Gemini embedding dimension)
- Metric: cosine similarity

**Document Metadata in Pinecone:**
```
{
  "id": "faq_001",
  "values": [0.234, -0.156, ..., 0.789],  // 768-dimensional vector
  "metadata": {
    "content": "Q: How do I understand my credit card statement? A: ...",
    "type": "faq",
    "category": "Credit Cards",
    "tags": ["credit_card", "statement"]
  }
}
```

## Chatbot RAG Workflow

When a user sends a message:

1. **Embedding Generation**
   - Convert user message to 768-dimensional vector using Gemini

2. **Context Retrieval**
   - Search Pinecone index for top-3 most similar documents
   - Rank by cosine similarity score

3. **Prompt Enhancement**
   - Build augmented prompt with:
     - System prompt (personality + guidelines)
     - Retrieved context (relevant KB documents)
     - User message

4. **Response Generation**
   - Send enhanced prompt to Gemini 3.1 Flash preview
   - Generate empathetic, context-aware response

5. **Response Return**
   - Return therapist's response to user

## Monitoring and Logging

All components use Python's `logging` module with the following logger:

```python
import logging
logger = logging.getLogger(__name__)
```

Configure logging level:
```python
logging.basicConfig(level=logging.INFO)  # or DEBUG for more detail
```

## Performance Optimization

### Embedding Caching
- Cache embeddings for frequently asked questions
- Reduce API calls for identical queries

### Batch Processing
- Process multiple scenarios/FAQs in batches
- Use bulk upsert operations for Pinecone

### Context Limiting
- Limit retrieved context to top-3 documents
- Truncate context to 300 characters per document

## Troubleshooting

### Issue: GEMINI_API_KEY not set
**Solution:** Ensure your `.env` file is loaded before running the script
```python
from dotenv import load_dotenv
load_dotenv()
```

### Issue: Pinecone index not found
**Solution:** Create the index first:
```python
from utils.vector_db import setup_and_seed_pinecone
setup_and_seed_pinecone()
```

### Issue: No relevant documents retrieved
**Solution:**
- Verify documents were loaded into Pinecone
- Check Pinecone index statistics
- Test with different queries
- Ensure embedding dimensions match (768)

### Issue: Incomplete RAG response
**Solution:**
- Check context retrieval is working
- Verify system prompt is loaded
- Test with RAG disabled: `chatbot.chat(message, use_rag=False)`

## Next Steps

1. **Fine-tuning**: Collect and train on real user interactions
2. **Evaluation**: Measure response quality and relevance
3. **Scaling**: Implement conversation history and multi-turn dialogs
4. **Monitoring**: Track response quality metrics
5. **Integration**: Deploy to API endpoints

## References

- [Gemini API Documentation](https://ai.google.dev/)
- [Pinecone Documentation](https://docs.pinecone.io/)
- [LangChain Documentation](https://python.langchain.com/)
- [RAG Best Practices](https://www.promptingguide.ai/)
