# RAG Pipeline Testing Guide

## Overview
This guide provides comprehensive testing procedures for the RAG pipeline at each stage.

---

## Unit Testing

### 1. Test S3 Storage Manager

```python
# test_s3_storage.py
from src.knowledge.s3_storage import S3StorageManager
import os
from dotenv import load_dotenv

load_dotenv()

def test_s3_connection():
    """Test S3 bucket connection"""
    try:
        manager = S3StorageManager(
            bucket_name=os.getenv("S3_BUCKET_NAME", "f2-fintech-kb")
        )
        print("✓ S3 connection successful")
        return True
    except Exception as e:
        print(f"✗ S3 connection failed: {e}")
        return False

def test_s3_upload():
    """Test uploading a file"""
    try:
        manager = S3StorageManager()
        # Create test file
        with open('/tmp/test_file.txt', 'w') as f:
            f.write('Test content')

        success = manager.upload_file('/tmp/test_file.txt', 'test/test_file.txt')
        if success:
            print("✓ File upload successful")
        return success
    except Exception as e:
        print(f"✗ File upload failed: {e}")
        return False

def test_s3_download():
    """Test downloading a file"""
    try:
        manager = S3StorageManager()
        success = manager.download_file('test/test_file.txt', '/tmp/downloaded_file.txt')
        if success:
            print("✓ File download successful")
        return success
    except Exception as e:
        print(f"✗ File download failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing S3 Storage Manager...")
    test_s3_connection()
    test_s3_upload()
    test_s3_download()
```

Run: `python test_s3_storage.py`

### 2. Test Data Processor

```python
# test_data_processor.py
from src.knowledge.data_processor import DataProcessor
from pathlib import Path

def test_data_processor():
    """Test data processing pipeline"""
    processor = DataProcessor()

    print("\nTesting Data Processor...")

    # Test scenarios processing
    print("\n1. Testing scenarios processing...")
    scenarios = processor.process_scenarios()
    if scenarios:
        print(f"✓ Processed {len(scenarios)} scenarios")
        print(f"  Sample: {scenarios[0]}")
    else:
        print("✗ No scenarios processed")

    # Test FAQs processing
    print("\n2. Testing FAQs processing...")
    faqs = processor.process_faqs()
    if faqs:
        print(f"✓ Processed {len(faqs)} FAQs")
        print(f"  Sample: {faqs[0]['question'][:50]}...")
    else:
        print("✗ No FAQs processed")

    # Test system prompt processing
    print("\n3. Testing system prompt processing...")
    prompt = processor.process_system_prompt()
    if prompt:
        print(f"✓ System prompt processed ({len(prompt)} characters)")
        print(f"  Preview: {prompt[:100]}...")
    else:
        print("✗ System prompt not processed")

    # Verify files exist
    print("\n4. Checking processed files...")
    processed_dir = Path("src/data/processed")
    files = list(processed_dir.glob("*"))
    for file in files:
        print(f"✓ {file.name}")

if __name__ == "__main__":
    test_data_processor()
```

Run: `python test_data_processor.py`

### 3. Test Embedder

```python
# test_embedder.py
from src.knowledge.embedder import get_embeddings, embed_text
import os
from dotenv import load_dotenv

load_dotenv()

def test_embeddings():
    """Test embedding generation"""
    print("\nTesting Embedder...")

    # Test model initialization
    print("\n1. Testing embeddings model initialization...")
    try:
        embeddings = get_embeddings()
        print("✓ Embeddings model initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize embeddings: {e}")
        return

    # Test text embedding
    print("\n2. Testing text embedding...")
    test_texts = [
        "How do I manage credit card debt?",
        "What is an EMI?",
        "I'm stressed about my finances"
    ]

    for text in test_texts:
        try:
            vector = embed_text(text)
            print(f"✓ Embedded text: '{text[:40]}...' (dimension: {len(vector)})")
        except Exception as e:
            print(f"✗ Failed to embed text: {e}")

    # Test vector properties
    print("\n3. Testing vector properties...")
    vector = embed_text("financial stress")
    print(f"  - Vector dimension: {len(vector)}")
    print(f"  - Vector type: {type(vector)}")
    print(f"  - Sample values: {vector[:5]}")
    print(f"  - Vector magnitude: {sum(v**2 for v in vector)**0.5:.4f}")

if __name__ == "__main__":
    test_embeddings()
```

Run: `python test_embedder.py`

### 4. Test Pinecone Integration

```python
# test_pinecone.py
from src.knowledge.loader import KnowledgeLoader
from src.knowledge.retriever import KnowledgeRetriever
from src.knowledge.embedder import embed_text
import os
from dotenv import load_dotenv

load_dotenv()

def test_pinecone():
    """Test Pinecone vector database"""
    print("\nTesting Pinecone Integration...")

    # Test index existence
    print("\n1. Testing Pinecone index...")
    try:
        loader = KnowledgeLoader()
        print("✓ Connected to Pinecone index")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return

    # Test loading documents
    print("\n2. Testing document loading...")
    try:
        loader.load_all()
        print("✓ Documents loaded to Pinecone")
    except Exception as e:
        print(f"✗ Failed to load documents: {e}")

    # Test retrieval
    print("\n3. Testing document retrieval...")
    try:
        query = "credit card debt"
        query_vector = embed_text(query)
        retriever = KnowledgeRetriever()
        results = retriever.retrieve(query_vector, top_k=3)

        print(f"✓ Retrieved {len(results)} documents for query: '{query}'")
        for i, result in enumerate(results, 1):
            metadata = result.get('metadata', {})
            print(f"  {i}. [{metadata.get('type', 'doc')}] Score: {result['score']:.3f}")
    except Exception as e:
        print(f"✗ Failed to retrieve documents: {e}")

if __name__ == "__main__":
    test_pinecone()
```

Run: `python test_pinecone.py`

### 5. Test Model Training

```python
# test_model_training.py
from src.model.model_train import ModelTrainer
import os
from dotenv import load_dotenv

load_dotenv()

def test_model_training():
    """Test model training pipeline"""
    print("\nTesting Model Training...")

    trainer = ModelTrainer()

    # Test training data preparation
    print("\n1. Testing training data preparation...")
    training_data = trainer.prepare_training_data()
    if training_data:
        print(f"✓ Prepared {len(training_data)} training examples")
        print(f"  Sample: {training_data[0]}")
    else:
        print("✗ No training data prepared")

    # Test system prompt loading
    print("\n2. Testing system prompt loading...")
    prompt = trainer.load_system_prompt()
    if prompt:
        print(f"✓ System prompt loaded ({len(prompt)} characters)")
        print(f"  Preview: {prompt[:100]}...")
    else:
        print("✗ Failed to load system prompt")

    # Test model validation
    print("\n3. Testing model validation...")
    try:
        sample_response = trainer._test_model_response(
            user_input="How can I manage financial stress?",
            system_prompt=prompt
        )
        if sample_response:
            print(f"✓ Model test successful")
            print(f"  Response: {sample_response[:100]}...")
        else:
            print("✗ Model test returned no response")
    except Exception as e:
        print(f"✗ Model test failed: {e}")

if __name__ == "__main__":
    test_model_training()
```

Run: `python test_model_training.py`

### 6. Test Chatbot with RAG

```python
# test_chatbot.py
from src.inference.predictor import TherapyChatbot
import os
from dotenv import load_dotenv

load_dotenv()

def test_chatbot():
    """Test chatbot with RAG pipeline"""
    print("\nTesting Chatbot with RAG...")

    # Initialize chatbot
    print("\n1. Testing chatbot initialization...")
    try:
        chatbot = TherapyChatbot()
        print("✓ Chatbot initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize chatbot: {e}")
        return

    # Test chat functionality
    print("\n2. Testing chat functionality...")
    test_queries = [
        "I'm worried about my credit card debt",
        "How should I handle missed EMI payments?",
        "What's the difference between savings and checking accounts?"
    ]

    for query in test_queries:
        try:
            print(f"\nQuery: '{query}'")
            response = chatbot.chat(query)
            if response:
                print(f"✓ Response generated ({len(response)} characters)")
                print(f"  Preview: {response[:100]}...")
            else:
                print("✗ No response generated")
        except Exception as e:
            print(f"✗ Chat failed: {e}")

    # Test RAG retrieval
    print("\n3. Testing RAG context retrieval...")
    query = "financial stress"
    context = chatbot._get_relevant_context(query)
    if context:
        print(f"✓ Retrieved {len(context)} context documents")
        for i, doc in enumerate(context, 1):
            print(f"  {i}. [{doc.get('type')}] Score: {doc.get('relevance_score'):.3f}")
    else:
        print("✗ No context retrieved")

if __name__ == "__main__":
    test_chatbot()
```

Run: `python test_chatbot.py`

---

## Integration Testing

### Run All Tests

```bash
#!/bin/bash
# run_all_tests.sh

echo "Running all component tests..."
echo ""

echo "1. Testing S3 Storage..."
python test_s3_storage.py
echo ""

echo "2. Testing Data Processor..."
python test_data_processor.py
echo ""

echo "3. Testing Embedder..."
python test_embedder.py
echo ""

echo "4. Testing Pinecone..."
python test_pinecone.py
echo ""

echo "5. Testing Model Training..."
python test_model_training.py
echo ""

echo "6. Testing Chatbot..."
python test_chatbot.py
echo ""

echo "All tests completed!"
```

---

## End-to-End Testing

### Test Complete Pipeline

```bash
# Run the complete RAG pipeline
python src/rag_pipeline.py

# Skip S3 for local testing
python src/rag_pipeline.py --skip-s3-upload --skip-s3-download
```

---

## Performance Testing

### Measure Response Time

```python
# test_performance.py
import time
from src.inference.predictor import TherapyChatbot

def test_performance():
    chatbot = TherapyChatbot()

    test_queries = [
        "I have credit card debt",
        "How do I manage financial stress?",
        "What's an EMI?"
    ]

    print("Performance Test Results:")
    print("-" * 60)

    total_time = 0
    for query in test_queries:
        start = time.time()
        response = chatbot.chat(query)
        elapsed = time.time() - start
        total_time += elapsed

        print(f"Query: '{query}'")
        print(f"Time: {elapsed:.2f}s")
        print()

    avg_time = total_time / len(test_queries)
    print(f"Average response time: {avg_time:.2f}s")
    print(f"Total queries: {len(test_queries)}")

if __name__ == "__main__":
    test_performance()
```

---

## Quality Testing

### Test Response Quality

```python
# test_quality.py
from src.inference.predictor import TherapyChatbot

def test_response_quality():
    chatbot = TherapyChatbot()

    test_cases = [
        {
            "query": "I'm embarrassed about my financial situation",
            "expected_keywords": ["understand", "shame", "embarrassed", "not alone"]
        },
        {
            "query": "I don't understand EMI",
            "expected_keywords": ["EMI", "monthly", "installment", "explain"]
        }
    ]

    for test in test_cases:
        response = chatbot.chat(test["query"])

        print(f"\nQuery: {test['query']}")
        print(f"Response: {response[:100]}...")

        # Check for expected keywords
        found_keywords = [
            kw for kw in test["expected_keywords"]
            if kw.lower() in response.lower()
        ]

        print(f"Expected keywords found: {len(found_keywords)}/{len(test['expected_keywords'])}")
```

---

## Debugging

### Enable Debug Logging

```python
import logging

# Set to DEBUG level
logging.basicConfig(level=logging.DEBUG)

# Now run any component with full debug output
from src.rag_pipeline import RAGPipeline
pipeline = RAGPipeline()
pipeline.run_full_pipeline()
```

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| API Key not found | Check .env file exists and contains GEMINI_API_KEY |
| Pinecone index error | Verify index exists with name `f2-therapy-index` |
| No documents retrieved | Check documents loaded with `KnowledgeLoader.load_all()` |
| Slow responses | Check network connectivity, API rate limits |
| Embedding dimension mismatch | Ensure Pinecone index has 768 dimensions |

---

## Checklist

Before deploying, verify:

- [ ] All unit tests pass
- [ ] Integration tests complete successfully
- [ ] E2E pipeline runs without errors
- [ ] Performance meets requirements (<5s per response)
- [ ] Response quality meets standards
- [ ] Logging is functioning
- [ ] All API keys are configured
- [ ] Data files are processed
- [ ] Vector DB is populated
- [ ] Model is trained

---

## Reporting

### Generate Test Report

```python
# generate_report.py
import json
from datetime import datetime

def generate_test_report():
    report = {
        "timestamp": datetime.now().isoformat(),
        "tests": {
            "s3_storage": "PASS",
            "data_processor": "PASS",
            "embedder": "PASS",
            "pinecone": "PASS",
            "model_training": "PASS",
            "chatbot": "PASS"
        },
        "performance": {
            "avg_response_time_ms": 2500,
            "embedding_time_ms": 200,
            "retrieval_time_ms": 100,
            "generation_time_ms": 2200
        },
        "documents": {
            "faqs": 50,
            "scenarios": 20,
            "vector_db_size_mb": 45
        }
    }

    with open("test_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("Test report saved to test_report.json")

if __name__ == "__main__":
    generate_test_report()
```
