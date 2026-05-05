"""
Process raw knowledge base files into formatted, ready-to-embed documents
"""

import json
import os
import hashlib
import stat
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def _validate_scenario_schema(scenario: dict) -> bool:
    """
    Validate scenario has required fields.

    Args:
        scenario: Scenario dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = {'id', 'title', 'content'}
    return all(field in scenario and scenario[field] for field in required_fields)

def _validate_faq_schema(faq: dict) -> bool:
    """
    Validate FAQ has required fields.

    Args:
        faq: FAQ dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = {'id', 'question', 'answer'}
    return all(field in faq and faq[field] for field in required_fields)

def _validate_conversation_schema(conversation: dict) -> bool:
    """
    Validate conversation has required fields.

    Args:
        conversation: Conversation dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = {'id', 'script'}
    return all(field in conversation and conversation[field] for field in required_fields)

def _set_secure_permissions(file_path: Path):
    """
    Set restrictive file permissions (0o600 - owner read/write only).

    Args:
        file_path: Path to file to secure
    """
    try:
        os.chmod(str(file_path), stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        logger.debug(f"Set secure permissions on {file_path}")
    except Exception as e:
        logger.warning(f"Could not set permissions on {file_path}: {e}")

def _content_signature(text: str) -> str:
    """Create a stable hash for change detection."""
    normalized = text.strip().replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

class DataProcessor:
    def __init__(self):
        self.raw_dir = Path("src/data/raw")
        self.processed_dir = Path("src/data/processed")

        # Create processed directory if it doesn't exist
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def _embedding_state_path(self):
        return self.processed_dir / ".embedding_state.json"

    def _load_embedding_state(self):
        state_path = self._embedding_state_path()
        if not state_path.exists():
            return {}

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            return state if isinstance(state, dict) else {}
        except Exception:
            logger.warning(f"Could not read embedding state from {state_path}; starting fresh")
            return {}

    def _save_embedding_state(self, state):
        state_path = self._embedding_state_path()
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _normalize_text(text):
        return str(text).strip().replace("\r\n", "\n")

    @classmethod
    def _hash_text(cls, text):
        return hashlib.sha256(cls._normalize_text(text).encode("utf-8")).hexdigest()

    def _record_key(self, source_name, item, index):
        record_id = item.get("id")
        if record_id:
            return str(record_id)

        return f"{source_name}_{self._record_hash(source_name, item)[:16]}"

    def _record_hash(self, source_name, item):
        stored = item.get("content_hash")
        if stored:
            return str(stored)

        return self._hash_text(self._build_processed_text(source_name, item))

    def _load_existing_processed_map(self, processed_file, source_name):
        if not processed_file.exists():
            return {}

        try:
            with open(processed_file, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            logger.warning(f"Could not read existing processed file {processed_file}; rebuilding it")
            return {}

        if not isinstance(records, list):
            return {}

        existing_map = {}
        for index, record in enumerate(records, start=1):
            if isinstance(record, dict):
                existing_map[self._record_key(source_name, record, index)] = record

        return existing_map

    @staticmethod
    def _has_embedding(record):
        embedding = record.get("embedding")
        return isinstance(embedding, list) and len(embedding) > 0

    def _build_processed_text(self, source_name, item):
        if source_name == "scenarios":
            return f"{item.get('title', '')}: {item.get('content', '')}".strip(': ')

        if source_name == "faqs":
            return f"Q: {item.get('question', '')}\nA: {item.get('answer', '')}".strip()

        if source_name == "conversation_training_data":
            parts = []
            title = item.get("title")
            category = item.get("category")
            if title:
                parts.append(f"Conversation: {title}")
            if category:
                parts.append(f"Category: {category}")
            parts.append(f"User: {item.get('user_input', '')}")
            parts.append(f"Assistant: {item.get('expected_response', '')}")
            user_intent = item.get("user_intent")
            stage = item.get("stage")
            if user_intent:
                parts.append(f"Intent: {user_intent}")
            if stage:
                parts.append(f"Stage: {stage}")
            return "\n".join(parts).strip()

        return item.get("content") or item.get("text") or item.get("question") or item.get("answer") or ""

    def process_scenarios(self):
        """Process raw scenarios into formatted documents."""
        raw_file = self.raw_dir / "scenarios_raw.json"
        processed_file = self.processed_dir / "scenarios.json"

        if not raw_file.exists():
            logger.warning(f"Raw scenarios file not found: {raw_file}")
            return []

        try:
            with open(raw_file, 'r', encoding='utf-8') as f:
                raw_scenarios = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in scenarios file: {e}")
            return []

        state = self._load_embedding_state()
        source_state = state.get("scenarios", {})
        existing_map = self._load_existing_processed_map(processed_file, "scenarios")

        processed_scenarios = []
        updated = False
        for scenario in raw_scenarios:
            # Validate schema
            if not _validate_scenario_schema(scenario):
                logger.warning(f"Invalid scenario schema, skipping: {scenario.get('id', 'unknown')}")
                continue

            record_key = self._record_key("scenarios", scenario, len(processed_scenarios) + 1)
            record_hash = self._record_hash("scenarios", scenario)
            existing_record = existing_map.get(record_key)

            if source_state.get(record_key) == record_hash and existing_record and self._has_embedding(existing_record):
                processed_scenarios.append(existing_record)
                continue

            processed = {
                "id": scenario.get("id"),
                "title": scenario.get("title"),
                "content": scenario.get("content"),
                "category": scenario.get("category"),
                "severity": scenario.get("severity"),
                "keywords": self._extract_keywords(
                    f"{scenario.get('title')} {scenario.get('content')}"
                ),
                "content_hash": self._record_hash("scenarios", scenario),
                "processed_at": datetime.utcnow().isoformat()
            }

            if existing_record and self._has_embedding(existing_record) and existing_record.get("content_hash") == record_hash:
                processed["embedding"] = existing_record["embedding"]

            processed_scenarios.append(processed)
            updated = True

        if not updated and processed_file.exists():
            logger.info(f"Scenarios already processed and embedded; skipping rewrite of {processed_file.name}")
            return processed_scenarios

        try:
            with open(processed_file, 'w', encoding='utf-8') as f:
                json.dump(processed_scenarios, f, indent=2, ensure_ascii=False)

            # Set secure permissions on the file
            _set_secure_permissions(processed_file)

            logger.info(f"Processed {len(processed_scenarios)} scenarios")
            return processed_scenarios
        except IOError as e:
            logger.error(f"Error writing processed scenarios: {e}")
            return []

    def process_faqs(self):
        """Process raw FAQs into formatted documents."""
        raw_file = self.raw_dir / "faqs_raw.json"
        processed_file = self.processed_dir / "faqs.json"

        if not raw_file.exists():
            logger.warning(f"Raw FAQs file not found: {raw_file}")
            return []

        try:
            with open(raw_file, 'r', encoding='utf-8') as f:
                raw_faqs = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in FAQs file: {e}")
            return []

        state = self._load_embedding_state()
        source_state = state.get("faqs", {})
        existing_map = self._load_existing_processed_map(processed_file, "faqs")

        processed_faqs = []
        updated = False
        for faq in raw_faqs:
            # Validate schema
            if not _validate_faq_schema(faq):
                logger.warning(f"Invalid FAQ schema, skipping: {faq.get('id', 'unknown')}")
                continue

            record_key = self._record_key("faqs", faq, len(processed_faqs) + 1)
            record_hash = self._record_hash("faqs", faq)
            existing_record = existing_map.get(record_key)

            if source_state.get(record_key) == record_hash and existing_record and self._has_embedding(existing_record):
                processed_faqs.append(existing_record)
                continue

            processed = {
                "id": faq.get("id"),
                "question": faq.get("question"),
                "answer": faq.get("answer"),
                "category": faq.get("category", "general"),
                "tags": faq.get("tags", []),
                "content_hash": record_hash,
                "processed_at": datetime.utcnow().isoformat()
            }
            if existing_record and self._has_embedding(existing_record) and existing_record.get("content_hash") == record_hash:
                processed["embedding"] = existing_record["embedding"]

            processed_faqs.append(processed)
            updated = True

        if not updated and processed_file.exists():
            logger.info(f"FAQs already processed and embedded; skipping rewrite of {processed_file.name}")
            return processed_faqs

        try:
            with open(processed_file, 'w', encoding='utf-8') as f:
                json.dump(processed_faqs, f, indent=2, ensure_ascii=False)

            # Set secure permissions on the file
            _set_secure_permissions(processed_file)

            logger.info(f"Processed {len(processed_faqs)} FAQs")
            return processed_faqs
        except IOError as e:
            logger.error(f"Error writing processed FAQs: {e}")
            return []

    def process_conversations(self):
        """Process raw conversations into training examples."""
        raw_file = self.raw_dir / "conversations.json"
        processed_file = self.processed_dir / "conversation_training_data.json"

        if not raw_file.exists():
            logger.warning(f"Raw conversations file not found: {raw_file}")
            return []

        try:
            with open(raw_file, 'r', encoding='utf-8') as f:
                raw_conversations = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in conversations file: {e}")
            return []

        state = self._load_embedding_state()
        source_state = state.get("conversation_training_data", {})
        existing_map = self._load_existing_processed_map(processed_file, "conversation_training_data")

        processed_examples = []
        updated = False
        for conversation in raw_conversations:
            if not _validate_conversation_schema(conversation):
                logger.warning(
                    f"Invalid conversation schema, skipping: {conversation.get('id', 'unknown')}"
                )
                continue

            script = conversation.get("script", [])
            example_index = 0

            for i in range(0, len(script) - 1, 2):
                user_msg = script[i]
                assistant_msg = script[i + 1]

                if not (
                    user_msg.get("role") == "user" and assistant_msg.get("role") == "assistant"
                ):
                    continue

                candidate = {
                    "id": f"{conversation.get('id')}_example_{example_index + 1:03d}",
                    "conversation_id": conversation.get("id"),
                    "title": conversation.get("title"),
                    "category": conversation.get("category"),
                    "tags": conversation.get("tags", []),
                    "difficulty": conversation.get("difficulty"),
                    "user_input": user_msg.get("text", ""),
                    "expected_response": assistant_msg.get("text", ""),
                    "user_intent": user_msg.get("intent", ""),
                    "stage": user_msg.get("stage", ""),
                    "risk_score": user_msg.get("risk_score", 0),
                }

                record_key = self._record_key("conversation_training_data", candidate, len(processed_examples) + 1)
                record_hash = self._record_hash("conversation_training_data", candidate)
                existing_record = existing_map.get(record_key)

                if source_state.get(record_key) == record_hash and existing_record and self._has_embedding(existing_record):
                    processed_examples.append(existing_record)
                    example_index += 1
                    continue

                example_index += 1
                candidate["id"] = f"{conversation.get('id')}_example_{example_index:03d}"
                candidate["content_hash"] = record_hash
                candidate["processed_at"] = datetime.utcnow().isoformat()

                if existing_record and self._has_embedding(existing_record) and existing_record.get("content_hash") == record_hash:
                    candidate["embedding"] = existing_record["embedding"]

                processed_examples.append(candidate)
                updated = True

        if not updated and processed_file.exists():
            logger.info(
                f"Conversation training data already processed and embedded; skipping rewrite of {processed_file.name}"
            )
            return processed_examples

        try:
            with open(processed_file, 'w', encoding='utf-8') as f:
                json.dump(processed_examples, f, indent=2, ensure_ascii=False)

            _set_secure_permissions(processed_file)

            logger.info(f"Processed {len(processed_examples)} conversation examples")
            return processed_examples
        except IOError as e:
            logger.error(f"Error writing processed conversations: {e}")
            return []

    def process_system_prompt(self):
        """Process raw system prompt."""
        raw_file = self.raw_dir / "system_prompt_raw.md"
        processed_file = self.processed_dir / "system_prompt.md"

        if not raw_file.exists():
            logger.warning(f"Raw system prompt not found: {raw_file}")
            return None

        try:
            with open(raw_file, 'r', encoding='utf-8') as f:
                content = f.read()

            processed_content = content.strip()

            state = self._load_embedding_state()
            system_state = state.get("system_prompt", {})
            existing_prompt = None

            if processed_file.exists():
                try:
                    with open(processed_file, 'r', encoding='utf-8') as f:
                        existing_prompt = f.read().strip()
                except Exception:
                    existing_prompt = None

            if system_state.get("system_prompt") == self._hash_text(processed_content) and existing_prompt == processed_content:
                logger.info("System prompt already processed and embedded; skipping rewrite")
                return processed_content

            with open(processed_file, 'w', encoding='utf-8') as f:
                f.write(processed_content)

            # Set secure permissions on the file
            _set_secure_permissions(processed_file)

            logger.info("Processed system prompt")
            return processed_content
        except IOError as e:
            logger.error(f"Error processing system prompt: {e}")
            return None

    def process_all(self):
        """Process all raw data into processed format."""
        logger.info("Starting data processing...")

        self.process_scenarios()
        self.process_faqs()
        self.process_conversations()
        self.process_system_prompt()

        logger.info("Data processing complete!")

    @staticmethod
    def _extract_keywords(text: str, limit: int = 10):
        """Extract keywords from text."""
        words = text.lower().split()
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        keywords = [w.strip('.,!?;:') for w in words
                   if len(w) > 3 and w not in stop_words]
        return list(set(keywords))[:limit]

if __name__ == "__main__":
    processor = DataProcessor()
    processor.process_all()
