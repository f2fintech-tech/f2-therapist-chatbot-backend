"""
Complete RAG Pipeline Orchestrator
Handles: S3 upload/download -> Data processing -> Embeddings -> Pinecone loading -> Model training

How to run the pipeline (from repository root):

- Activate the project's virtual environment (if using the included .venv):
    python -m venv .venv && source .venv/bin/activate

- Run the full pipeline (flags are optional):
    python src/rag_pipeline.py [--skip-s3-upload] [--skip-s3-download] [--skip-chatbot-test]

- Example: run processing, embeddings and loading locally, skipping S3 and chatbot test:
    python src/rag_pipeline.py --skip-s3-upload --skip-s3-download --skip-chatbot-test

- Run specific steps with `--steps` (comma-separated numbers 1-7). Example to run steps 3-5:
    python src/rag_pipeline.py --steps 3,4,5

- Notes:
    - Ensure required environment variables are set: `AWS_S3_BUCKET_NAME`, `AWS_REGION`, `PINECONE_API_KEY`, `GEMINI_API_KEY`.
    - The script expects processed JSON under `src/data/processed/` and will write state files there.
    - Use `--skip-chatbot-test` to avoid generating live model responses during test runs.

"""

import logging
import os
import json
import hashlib
import re
import time
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import pipeline components
from knowledge.s3_storage import S3StorageManager
from knowledge.data_processor import DataProcessor
from knowledge.embedder import get_embeddings
from knowledge.loader import KnowledgeLoader
try:
    from src.inference.predictor import TherapyChatbot
except ImportError:
    from inference.predictor import TherapyChatbot
from model.model_train import ModelTrainer


class DailyEmbeddingQuotaExceeded(RuntimeError):
    """Raised when embedding daily quota is exhausted and retries will not help."""


class RAGPipeline:
    """Orchestrates the complete RAG pipeline"""

    def __init__(self):
        logger.info("Initializing RAG Pipeline...")
        self.s3_manager = None
        self.data_processor = DataProcessor()
        self.knowledge_loader = None
        self.model_trainer = None
        self._next_embedding_request_at = 0.0
        self._adaptive_embed_delay = 0.75

    @staticmethod
    def _normalize_text(text):
        return str(text).strip().replace("\r\n", "\n")

    @classmethod
    def _hash_text(cls, text):
        return hashlib.sha256(cls._normalize_text(text).encode("utf-8")).hexdigest()

    def _embedding_state_path(self):
        return Path("src/data/processed/.embedding_state.json")

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

    def _record_key(self, source_name, item, index):
        record_id = item.get("id")
        if record_id:
            return str(record_id)

        return f"{source_name}_{self._record_hash(source_name, item)[:16]}"

    def _record_hash(self, source_name, item):
        stored = item.get("content_hash")
        if stored:
            return str(stored)

        return self._hash_text(self._build_embedding_text(source_name, item))

    @staticmethod
    def _retry_delay_from_error(msg, default_delay=20.0):
        retry_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", msg, re.IGNORECASE)
        return float(retry_match.group(1)) if retry_match else default_delay

    @staticmethod
    def _is_daily_quota_exhausted(msg):
        lowered = msg.lower()
        return (
            "embedcontentrequestsperdayperprojectpermodel-freetier" in lowered
            or "quota exceeded for metric" in lowered and "embed_content" in lowered
            or "exceeded your current quota" in lowered
        )

    def _wait_for_embedding_slot(self):
        now = time.time()
        wait = self._next_embedding_request_at - now
        if wait > 0:
            time.sleep(wait)

    def _mark_embedding_result(self, quota_hit=False):
        if quota_hit:
            self._adaptive_embed_delay = min(8.0, max(0.8, self._adaptive_embed_delay * 1.6))
        else:
            self._adaptive_embed_delay = max(0.35, self._adaptive_embed_delay * 0.92)

        self._next_embedding_request_at = time.time() + self._adaptive_embed_delay

    def _embed_query_with_retry(self, embeddings, text, label, item_id, max_retries=5):
        for attempt in range(1, max_retries + 1):
            try:
                self._wait_for_embedding_slot()
                vector = embeddings.embed_query(text)
                self._mark_embedding_result(quota_hit=False)
                return vector
            except Exception as exc:
                msg = str(exc)
                is_quota = "RESOURCE_EXHAUSTED" in msg or "429" in msg
                if is_quota and self._is_daily_quota_exhausted(msg):
                    raise DailyEmbeddingQuotaExceeded(msg)
                if not is_quota or attempt == max_retries:
                    raise

                self._mark_embedding_result(quota_hit=True)
                delay = self._retry_delay_from_error(msg)
                logger.warning(
                    f"Quota hit while embedding {label} {item_id}; retrying in {delay:.1f}s "
                    f"(attempt {attempt}/{max_retries})"
                )
                time.sleep(delay)

        raise RuntimeError(f"Failed to embed {label} {item_id}")

    def _embed_documents_batch_with_retry(self, embeddings, texts, label, max_retries=5):
        for attempt in range(1, max_retries + 1):
            try:
                self._wait_for_embedding_slot()
                vectors = embeddings.embed_documents(texts)
                self._mark_embedding_result(quota_hit=False)
                return vectors
            except Exception as exc:
                msg = str(exc)
                is_quota = "RESOURCE_EXHAUSTED" in msg or "429" in msg
                if is_quota and self._is_daily_quota_exhausted(msg):
                    raise DailyEmbeddingQuotaExceeded(msg)
                if not is_quota or attempt == max_retries:
                    raise

                self._mark_embedding_result(quota_hit=True)
                delay = self._retry_delay_from_error(msg)
                logger.warning(
                    f"Quota hit while embedding {label} batch of {len(texts)}; retrying in {delay:.1f}s "
                    f"(attempt {attempt}/{max_retries})"
                )
                time.sleep(delay)

        raise RuntimeError(f"Failed to embed {label} batch")

    def _build_embedding_text(self, source_name, item):
        """Build embedding text for a processed record."""
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

        content = item.get("content") or item.get("text") or item.get("question") or item.get("answer") or ""
        return str(content).strip()

    def _embed_json_collection(self, file_path, embeddings):
        """Embed a processed JSON collection in place."""
        with open(file_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        if not isinstance(records, list):
            logger.warning(f"Skipping non-list JSON collection: {file_path}")
            return False

        source_name = file_path.stem
        state = self._load_embedding_state()
        source_state = state.setdefault(source_name, {})
        updated = False
        embedded_count = 0
        skipped_count = 0

        if source_name == "conversation_training_data":
            default_batch_size = "1"
            default_batch_pause = "1.8"
            default_record_pause = "1.4"
        else:
            default_batch_size = "4"
            default_batch_pause = "0.6"
            default_record_pause = "0.3"

        batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", default_batch_size))
        batch_pause_seconds = float(os.getenv("EMBEDDING_BATCH_PAUSE_SECONDS", default_batch_pause))
        record_pause_seconds = float(os.getenv("EMBEDDING_RECORD_PAUSE_SECONDS", default_record_pause))

        pending_records = []
        quota_exhausted = False

        for idx, item in enumerate(records, start=1):
            if not isinstance(item, dict):
                skipped_count += 1
                logger.warning(f"Skipping non-object record in {file_path}: index {idx}")
                continue

            record_key = self._record_key(source_name, item, idx)
            record_hash = self._record_hash(source_name, item)

            if source_state.get(record_key) == record_hash:
                continue

            text = self._build_embedding_text(source_name, item)
            if not text:
                skipped_count += 1
                logger.warning(f"Skipping empty embedding text for {file_path} record {item.get('id', idx)}")
                continue

            pending_records.append((idx, item, record_key, record_hash, text))

        cursor = 0
        current_batch_size = max(1, batch_size)

        while cursor < len(pending_records):
            batch = pending_records[cursor:cursor + current_batch_size]
            texts = [entry[4] for entry in batch]

            try:
                vectors = self._embed_documents_batch_with_retry(embeddings, texts, source_name)
                if len(vectors) != len(batch):
                    if len(vectors) == 1 and len(batch) > 1:
                        next_size = max(1, current_batch_size // 2)
                        if next_size == current_batch_size:
                            next_size = 1
                        logger.warning(
                            f"Embedding API returned 1 vector for batch size {len(batch)} in "
                            f"{file_path.name}; reducing batch size to {next_size}."
                        )
                        current_batch_size = next_size
                        continue

                    raise RuntimeError(
                        f"Embedding batch size mismatch for {file_path.name}: "
                        f"expected {len(batch)}, got {len(vectors)}"
                    )

                for (_, item, record_key, record_hash, _), vector in zip(batch, vectors):
                    item["embedding"] = vector
                    item["content_hash"] = record_hash
                    embedded_count += 1
                    updated = True
                    source_state[record_key] = record_hash

                cursor += len(batch)

            except DailyEmbeddingQuotaExceeded as exc:
                quota_exhausted = True
                logger.error(
                    "Daily embedding quota exhausted while processing %s. "
                    "Stopping further embedding attempts for now. Error: %s",
                    file_path.name,
                    exc,
                )
                break

            except Exception as exc:
                logger.warning(
                    f"Batch embedding failed for {file_path.name} (size {len(batch)}). "
                    f"Falling back to per-record embedding. Error: {exc}"
                )
                for position, (idx, item, record_key, record_hash, text) in enumerate(batch):
                    try:
                        item["embedding"] = self._embed_query_with_retry(
                            embeddings, text, source_name, item.get("id", idx)
                        )
                        item["content_hash"] = record_hash
                        embedded_count += 1
                        updated = True
                        source_state[record_key] = record_hash

                        if position + 1 < len(batch) and record_pause_seconds > 0:
                            time.sleep(record_pause_seconds)
                    except DailyEmbeddingQuotaExceeded as record_quota_exc:
                        quota_exhausted = True
                        logger.error(
                            "Daily embedding quota exhausted while processing %s record %s. "
                            "Stopping further embedding attempts for now. Error: %s",
                            file_path.name,
                            item.get("id", idx),
                            record_quota_exc,
                        )
                        break
                    except Exception as record_exc:
                        skipped_count += 1
                        logger.error(
                            f"Error embedding {file_path} record {item.get('id', idx)}: {record_exc}"
                        )

                if quota_exhausted:
                    break

                cursor += len(batch)

            if cursor < len(pending_records) and batch_pause_seconds > 0:
                time.sleep(batch_pause_seconds)

        if updated:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
            self._save_embedding_state(state)

        if quota_exhausted:
            logger.warning(
                "Embedding paused due to daily quota exhaustion for %s. "
                "Re-run after quota reset to continue from saved progress.",
                file_path.name,
            )

        if embedded_count:
            logger.info(
                f"Embedded {embedded_count} records in {file_path.name} "
                f"({skipped_count} skipped)"
            )
        else:
            logger.warning(f"No new embeddings written for {file_path.name}")

        return embedded_count > 0

    def _embed_system_prompt(self, embeddings):
        """Embed the processed system prompt as a single-record collection."""
        prompt_path = Path("src/data/processed/system_prompt.md")
        if not prompt_path.exists():
            logger.warning(f"System prompt not found at {prompt_path}")
            return False

        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read().strip()

        if not prompt_text:
            logger.warning("System prompt file is empty, skipping embedding")
            return False

        output_path = Path("src/data/processed/system_prompt.json")
        if output_path.exists():
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    existing_records = json.load(f)
                if isinstance(existing_records, list) and existing_records:
                    existing_record = existing_records[0]
                    if (
                        existing_record.get("content") == prompt_text
                        and isinstance(existing_record.get("embedding"), list)
                        and existing_record["embedding"]
                    ):
                        return True
            except Exception as e:
                # Log exception for debugging instead of silently failing
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to check system prompt in vector store: {e}")

        record = {
            "id": "system_prompt",
            "source_file": "system_prompt.md",
            "content": prompt_text,
            "content_hash": self._hash_text(prompt_text),
            "embedding": self._embed_query_with_retry(
                embeddings, prompt_text, "system_prompt", "system_prompt"
            )
        }

        state = self._load_embedding_state()
        state.setdefault("system_prompt", {})["system_prompt"] = record["content_hash"]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([record], f, indent=2, ensure_ascii=False)

        self._save_embedding_state(state)

        logger.info("Embedded system prompt into system_prompt.json")
        return True

    def step_1_upload_to_s3(self):
        """Step 1: Upload raw knowledge base files to S3"""
        logger.info("\n" + "="*60)
        logger.info("STEP 1: Uploading raw KB files to S3")
        logger.info("="*60)

        try:
            self.s3_manager = S3StorageManager(
                bucket_name=os.getenv("AWS_S3_BUCKET_NAME", "f2-fintech-knowledge-base"),
                region=os.getenv("AWS_REGION", "ap-south-1")
            )

            raw_dir = Path("src/data/raw")
            if not raw_dir.exists():
                logger.error(f"Raw data directory not found: {raw_dir}")
                return False

            logger.info(f"Uploading files from {raw_dir}...")
            success = self.s3_manager.sync_raw_to_s3()

            if success:
                logger.info("✓ Successfully uploaded raw KB files to S3")
            else:
                logger.error("✗ Failed to upload some files to S3")

            return success

        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            return False

    def step_2_download_from_s3(self):
        """Step 2: Download knowledge base files from S3"""
        logger.info("\n" + "="*60)
        logger.info("STEP 2: Downloading KB files from S3")
        logger.info("="*60)

        try:
            if self.s3_manager is None:
                self.s3_manager = S3StorageManager(
                    bucket_name=os.getenv("AWS_S3_BUCKET_NAME", "f2-fintech-knowledge-base"),
                    region=os.getenv("AWS_REGION", "ap-south-1")
                )

            logger.info("Downloading raw files from S3...")
            success = self.s3_manager.download_raw_from_s3()

            if success:
                logger.info("✓ Successfully downloaded raw KB files from S3")
            else:
                logger.error("✗ Failed to download some files from S3")

            return success

        except Exception as e:
            logger.error(f"Error downloading from S3: {e}")
            return False

    def step_3_process_data(self):
        """Step 3: Process raw KB files into formatted documents"""
        logger.info("\n" + "="*60)
        logger.info("STEP 3: Processing raw KB files")
        logger.info("="*60)

        try:
            logger.info("Processing FAQs...")
            faqs = self.data_processor.process_faqs()
            if faqs:
                logger.info(f"✓ Processed {len(faqs)} FAQs")
            else:
                logger.warning("⚠ No FAQs found to process")

            logger.info("Processing scenarios...")
            scenarios = self.data_processor.process_scenarios()
            if scenarios:
                logger.info(f"✓ Processed {len(scenarios)} scenarios")
            else:
                logger.warning("⚠ No scenarios found to process")

            logger.info("Processing conversations...")
            conversations = self.data_processor.process_conversations()
            if conversations:
                logger.info(f"✓ Processed {len(conversations)} conversation examples")
            else:
                logger.warning("⚠ No conversation examples found to process")

            logger.info("Processing system prompt...")
            prompt = self.data_processor.process_system_prompt()
            if prompt:
                logger.info("✓ Processed system prompt")
            else:
                logger.warning("⚠ No system prompt found to process")

            return True

        except Exception as e:
            logger.error(f"Error processing data: {e}")
            return False

    def step_4_embed_data(self):
        """Step 4: Generate embeddings for processed documents"""
        logger.info("\n" + "="*60)
        logger.info("STEP 4: Generating embeddings for KB documents")
        logger.info("="*60)

        try:
            logger.info("Initializing embeddings model (Gemini gemini-embedding-2)...")
            embeddings = get_embeddings()
            logger.info("✓ Embeddings model ready")

            processed_dir = Path("src/data/processed")
            if not processed_dir.exists():
                logger.error(f"Processed data directory not found: {processed_dir}")
                return False

            collections = [
                path for path in sorted(processed_dir.glob("*.json"))
                if path.name != "system_prompt.json"
            ]

            if not collections and not (processed_dir / "system_prompt.md").exists():
                logger.error("No processed collections found. Run Step 3 before Step 4.")
                return False

            any_embedded = False

            if (processed_dir / "system_prompt.md").exists():
                any_embedded = self._embed_system_prompt(embeddings) or any_embedded

            for collection_path in collections:
                any_embedded = self._embed_json_collection(collection_path, embeddings) or any_embedded

            if not any_embedded:
                logger.warning("No embeddings were written during Step 4.")
                return False

            logger.info("✓ Embedding step completed for all processed collections")
            return True

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return False

    def step_5_load_to_pinecone(self):
        """Step 5: Load processed KB and embeddings to Pinecone"""
        logger.info("\n" + "="*60)
        logger.info("STEP 5: Loading KB documents to Pinecone vector DB")
        logger.info("="*60)

        try:
            logger.info("Initializing Pinecone index...")
            self.knowledge_loader = KnowledgeLoader()

            logger.info("Loading all documents to Pinecone...")
            self.knowledge_loader.load_all()

            logger.info("✓ Successfully loaded KB to Pinecone")
            return True

        except Exception as e:
            logger.error(f"Error loading to Pinecone: {e}")
            return False

    def step_6_train_model(self):
        """Step 6: Train model with Gemini 3.Flash preview"""
        logger.info("\n" + "="*60)
        logger.info("STEP 6: Training model with Gemini 3 Flash preview")
        logger.info("="*60)

        try:
            self.model_trainer = ModelTrainer()
            logger.info("Training model...")
            success = self.model_trainer.train()

            if success:
                logger.info("✓ Model training completed successfully")
            else:
                logger.warning("⚠ Model training completed with warnings")

            return True

        except Exception as e:
            logger.error(f"Error training model: {e}")
            return False

    def step_7_test_chatbot(self):
        """Step 7: Test chatbot RAG pipeline"""
        logger.info("\n" + "="*60)
        logger.info("STEP 7: Testing chatbot RAG pipeline")
        logger.info("="*60)

        try:
            logger.info("Initializing chatbot...")
            chatbot = TherapyChatbot()

            # Test queries
            test_queries = [
                "I'm worried about my credit card debt",
                "How should I handle missed EMI payments?",
                "What's the difference between a savings and checking account?"
            ]

            for query in test_queries:
                logger.info(f"\nTesting query: '{query}'")
                response = chatbot.chat(query)
                logger.info(f"Response: {response[:100]}...")

            logger.info("✓ Chatbot testing completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error testing chatbot: {e}")
            return False

    def run_full_pipeline(self, skip_s3_upload=False, skip_s3_download=False, skip_chatbot_test=False):
        """
        Run the complete RAG pipeline

        Args:
            skip_s3_upload: Skip uploading to S3 (useful if files already uploaded)
            skip_s3_download: Skip downloading from S3 (useful if running with local files)
            skip_chatbot_test: Skip chatbot testing step (Step 7)
        """
        logger.info("\n" + "█"*60)
        logger.info("█ STARTING COMPLETE RAG PIPELINE EXECUTION")
        logger.info("█"*60)

        steps = []

        # Step 1: Upload to S3
        if not skip_s3_upload:
            logger.info("\nStep 1/7: Upload to S3")
            if self.step_1_upload_to_s3():
                steps.append(("✓", "Upload to S3"))
            else:
                steps.append(("✗", "Upload to S3"))

        # Step 2: Download from S3
        if not skip_s3_download:
            logger.info("\nStep 2/7: Download from S3")
            if self.step_2_download_from_s3():
                steps.append(("✓", "Download from S3"))
            else:
                steps.append(("✗", "Download from S3"))

        # Step 3: Process data
        logger.info("\nStep 3/7: Process data")
        if self.step_3_process_data():
            steps.append(("✓", "Process data"))
        else:
            steps.append(("✗", "Process data"))

        # Step 4: Generate embeddings
        logger.info("\nStep 4/7: Generate embeddings")
        embed_success = self.step_4_embed_data()
        if embed_success:
            steps.append(("✓", "Generate embeddings"))
        else:
            steps.append(("✗", "Generate embeddings"))
            logger.error("Stopping pipeline because Step 4 failed.")
            return False

        # Step 5: Load to Pinecone
        logger.info("\nStep 5/7: Load to Pinecone")
        if self.step_5_load_to_pinecone():
            steps.append(("✓", "Load to Pinecone"))
        else:
            steps.append(("✗", "Load to Pinecone"))

        # Step 6: Train model
        logger.info("\nStep 6/7: Train model")
        if self.step_6_train_model():
            steps.append(("✓", "Train model"))
        else:
            steps.append(("✗", "Train model"))

        # Step 7: Test chatbot
        if skip_chatbot_test:
            logger.info("\nStep 7/7: Test chatbot (SKIPPED)")
            steps.append(("-", "Test chatbot (skipped)"))
        else:
            logger.info("\nStep 7/7: Test chatbot")
            if self.step_7_test_chatbot():
                steps.append(("✓", "Test chatbot"))
            else:
                steps.append(("✗", "Test chatbot"))

        # Print summary
        logger.info("\n" + "█"*60)
        logger.info("█ PIPELINE EXECUTION SUMMARY")
        logger.info("█"*60)
        for symbol, step_name in steps:
            logger.info(f"{symbol} {step_name}")

        success_count = sum(1 for symbol, _ in steps if symbol == "✓")
        total_steps = len(steps)
        logger.info(f"\nCompleted: {success_count}/{total_steps} steps")

        if success_count == total_steps:
            logger.info("\n🎉 RAG PIPELINE EXECUTION SUCCESSFUL!")
        else:
            logger.warning(f"\n⚠ Pipeline completed with {total_steps - success_count} failures")

        logger.info("█"*60 + "\n")

        return success_count == total_steps


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="RAG Pipeline Orchestrator")
    parser.add_argument("--skip-s3-upload", action="store_true", help="Skip S3 upload step")
    parser.add_argument("--skip-s3-download", action="store_true", help="Skip S3 download step")
    parser.add_argument("--skip-chatbot-test", action="store_true", help="Skip chatbot testing step")
    parser.add_argument("--steps", type=str, help="Comma-separated specific steps to run (1-7)")

    args = parser.parse_args()

    pipeline = RAGPipeline()
    pipeline.run_full_pipeline(
        skip_s3_upload=args.skip_s3_upload,
        skip_s3_download=args.skip_s3_download,
        skip_chatbot_test=args.skip_chatbot_test,
    )


if __name__ == "__main__":
    main()
