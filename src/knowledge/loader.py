"""
Loads knowledge base documents into Pinecone
"""

import json
import logging
from pathlib import Path
from pinecone import Pinecone
import os

logger = logging.getLogger(__name__)


def _safe_metadata(value, default=None):
    """Return Pinecone-compatible metadata values."""
    if value is None:
        return "unknown" if default is None else default
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [str(v) for v in value]
    return str(value)

class KnowledgeLoader:
    def __init__(self):
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY is not set! Please configure it in your environment.")

        index_name = "f2-therapy-index"
        self.client = Pinecone(api_key=api_key)
        self.index = self.client.Index(index_name)

    def _record_text(self, source_name, record):
        """Build searchable text for a processed record."""
        if source_name == "scenarios":
            return f"{record.get('title', '')}: {record.get('content', '')}".strip(': ')

        if source_name == "faqs":
            return f"Q: {record.get('question', '')}\nA: {record.get('answer', '')}".strip()

        if source_name == "conversation_training_data":
            parts = []
            title = record.get("title")
            category = record.get("category")
            if title:
                parts.append(f"Conversation: {title}")
            if category:
                parts.append(f"Category: {category}")
            parts.append(f"User: {record.get('user_input', '')}")
            parts.append(f"Assistant: {record.get('expected_response', '')}")
            user_intent = record.get("user_intent")
            stage = record.get("stage")
            if user_intent:
                parts.append(f"Intent: {user_intent}")
            if stage:
                parts.append(f"Stage: {stage}")
            return "\n".join(parts).strip()

        if source_name == "system_prompt":
            return record.get("content", "")

        return record.get("content") or record.get("text") or record.get("question") or record.get("answer") or ""

    def _load_json_collection(self, collection_path):
        """Load a processed JSON collection into Pinecone."""
        if not collection_path.exists():
            logger.warning(f"Processed collection not found at {collection_path}")
            return 0

        with open(collection_path, 'r', encoding='utf-8') as f:
            records = json.load(f)

        if not isinstance(records, list):
            logger.warning(f"Skipping non-list JSON collection: {collection_path}")
            return 0

        vectors = []
        skipped = 0
        source_name = collection_path.stem

        for record in records:
            if not isinstance(record, dict):
                skipped += 1
                continue

            vector = record.get("embedding")
            if not vector:
                skipped += 1
                logger.warning(
                    f"Missing embedding for {source_name} record {record.get('id', 'unknown')}"
                )
                continue

            record_id = record.get("id")
            if not record_id:
                skipped += 1
                logger.warning(f"Missing id in {collection_path.name}, skipping record")
                continue

            content = self._record_text(source_name, record)
            metadata = {
                key: _safe_metadata(value)
                for key, value in record.items()
                if key != "embedding"
            }
            metadata["type"] = source_name
            metadata["content"] = content
            metadata["source_file"] = collection_path.name

            vectors.append({
                'id': str(record_id),
                'values': vector,
                'metadata': metadata
            })

        if not vectors:
            logger.warning(f"No loadable vectors found in {collection_path.name}")
            return 0

        self.index.upsert(vectors=vectors)
        logger.info(
            f"Loaded {len(vectors)} records from {collection_path.name} into Pinecone"
            + (f" ({skipped} skipped)" if skipped else "")
        )
        return len(vectors)
    
    def load_scenarios(self):
        """Load scenarios from JSON into vector DB."""
        scenarios_path = Path("src/data/processed/scenarios.json")
        return self._load_json_collection(scenarios_path)
    
    def load_faqs(self):
        """Load FAQs from JSON into vector DB."""
        faqs_path = Path("src/data/processed/faqs.json")
        return self._load_json_collection(faqs_path)
    
    def load_all(self):
        """Load all knowledge base documents."""
        logger.info("Loading knowledge base into Pinecone...")

        processed_dir = Path("src/data/processed")
        if not processed_dir.exists():
            logger.warning(f"Processed directory not found at {processed_dir}")
            return False

        total_loaded = 0
        for collection_path in sorted(processed_dir.glob("*.json")):
            total_loaded += self._load_json_collection(collection_path)

        logger.info(f"Knowledge base loaded successfully! Total vectors loaded: {total_loaded}")
        return total_loaded > 0

if __name__ == "__main__":
    loader = KnowledgeLoader()
    loader.load_all()