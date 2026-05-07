"""
Incremental document processor: only processes documents that have changed.
Reduces API calls and processing time by skipping unchanged documents.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.knowledge.ingestion_state import IngestionState

logger = logging.getLogger(__name__)


class IncrementalProcessor:
    """
    Process only changed/new documents while maintaining state for resumability.
    Integrates with IngestionState to avoid re-processing unchanged content.
    """
    
    def __init__(self, state_file: Optional[Path] = None, batch_size: int = 10):
        """
        Initialize incremental processor.
        
        Args:
            state_file: Path to ingestion state JSON
            batch_size: Number of documents to process in each batch
        """
        self.state = IngestionState(state_file)
        self.batch_size = batch_size
        self.processed_count = 0
        self.skipped_count = 0
        self.failed_count = 0
    
    def detect_changes(self, docs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect which documents have changed since last processing.
        
        Args:
            docs: Dict of {doc_id: {content, metadata, source, ...}}
        
        Returns:
            {
                "changed": {...docs that changed...},
                "unchanged": {...docs that are already embedded...},
                "removed": [...doc_ids that are no longer present...]
            }
        """
        changed = {}
        unchanged = {}
        
        for doc_id, doc_data in docs.items():
            content = doc_data.get("content", "")
            source = doc_data.get("source", "unknown")
            
            if self.state.is_changed(doc_id, content, source):
                changed[doc_id] = doc_data
            else:
                unchanged[doc_id] = doc_data
        
        # Detect removed documents (were in state but not in current docs)
        removed = [
            doc_id for doc_id in self.state.state["documents"]
            if doc_id not in docs
        ]
        
        summary = {
            "changed": changed,
            "unchanged": unchanged,
            "removed": removed,
            "changed_count": len(changed),
            "unchanged_count": len(unchanged),
            "removed_count": len(removed)
        }
        
        logger.info(
            f"Change detection: {len(changed)} changed, "
            f"{len(unchanged)} unchanged, {len(removed)} removed"
        )
        
        return summary
    
    def process_batch(
        self,
        docs: Dict[str, Dict[str, Any]],
        processor_fn,
        resume_from_failed: bool = False
    ) -> Dict[str, Any]:
        """
        Process documents in batches, calling processor_fn for each.
        Tracks state and allows resuming from failures.
        
        Args:
            docs: Dict of {doc_id: {content, metadata, source, ...}}
            processor_fn: Async function to process a doc. Called as:
                         processor_fn(doc_id, doc_data, state)
            resume_from_failed: If True, retry previously failed documents
        
        Returns:
            {
                "processed": int,
                "skipped": int,
                "failed": int,
                "errors": [...]
            }
        """
        # Optionally clear stale 'processing' flags from previous crashed runs
        if resume_from_failed:
            self.state.clear_processing_flags()
        
        # Detect what's changed
        changes = self.detect_changes(docs)
        docs_to_process = changes["changed"]
        
        if not docs_to_process:
            logger.info("No changed documents to process")
            return {
                "processed": 0,
                "skipped": changes["unchanged_count"],
                "failed": 0,
                "errors": []
            }
        
        errors = []
        
        # Process in batches
        doc_ids = list(docs_to_process.keys())
        for batch_start in range(0, len(doc_ids), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(doc_ids))
            batch_ids = doc_ids[batch_start:batch_end]
            
            logger.info(
                f"Processing batch {batch_start // self.batch_size + 1}: "
                f"docs {batch_start + 1}-{batch_end} of {len(doc_ids)}"
            )
            
            for doc_id in batch_ids:
                doc_data = docs_to_process[doc_id]
                source = doc_data.get("source", "unknown")
                
                try:
                    # Mark as processing
                    self.state.mark_processing(doc_id, source, doc_data.get("metadata"))
                    self.state.save()
                    
                    # Call processor function
                    processor_fn(doc_id, doc_data, self.state)
                    
                    # Mark as embedded
                    content = doc_data.get("content", "")
                    vector_id = doc_data.get("vector_id", f"{source}_{doc_id}")
                    self.state.mark_embedded(
                        doc_id,
                        content,
                        source,
                        vector_id,
                        doc_data.get("metadata")
                    )
                    self.processed_count += 1
                    
                except Exception as e:
                    error_msg = f"Failed to process {doc_id}: {str(e)}"
                    logger.error(error_msg)
                    self.state.mark_failed(doc_id, str(e), source)
                    self.failed_count += 1
                    errors.append(error_msg)
                
                finally:
                    self.state.save()
        
        # Mark sync complete
        self.state.mark_sync_complete()
        self.state.save()
        
        self.skipped_count = changes["unchanged_count"]
        
        result = {
            "processed": self.processed_count,
            "skipped": self.skipped_count,
            "failed": self.failed_count,
            "errors": errors,
            "unchanged": changes["unchanged_count"],
            "removed": changes["removed_count"]
        }
        
        logger.info(f"Batch processing complete: {result}")
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current ingestion statistics."""
        return self.state.get_stats()
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        return (
            f"Incremental Processing Summary:\n"
            f"  Processed: {self.processed_count}\n"
            f"  Skipped (unchanged): {self.skipped_count}\n"
            f"  Failed: {self.failed_count}\n"
            f"\n{self.state.get_summary()}"
        )


class IncrementalDataProcessor:
    """
    Wraps DataProcessor to enable incremental updates.
    Only processes documents that have changed.
    """
    
    def __init__(self, data_processor_instance, state_file: Optional[Path] = None):
        """
        Initialize incremental wrapper.
        
        Args:
            data_processor_instance: Instance of src/knowledge/data_processor.py::DataProcessor
            state_file: Path to ingestion state JSON
        """
        self.data_processor = data_processor_instance
        self.incremental = IncrementalProcessor(state_file)
    
    def process_faqs_incremental(self, faqs: List[Dict]) -> Dict[str, Any]:
        """
        Process FAQs incrementally, skipping unchanged ones.
        
        Args:
            faqs: List of FAQ dicts with 'id', 'question', 'answer'
        
        Returns:
            Details of what was processed
        """
        # Build doc map for change detection
        docs = {}
        for faq in faqs:
            doc_id = faq.get("id", "")
            if not doc_id:
                continue
            
            # Combine question + answer as content for hashing
            content = f"{faq.get('question', '')}\n{faq.get('answer', '')}"
            docs[doc_id] = {
                "content": content,
                "data": faq,
                "source": "faqs",
                "metadata": {
                    "category": faq.get("category", "general"),
                    "tags": faq.get("tags", [])
                }
            }
        
        # Process only changed ones
        def process_faq(doc_id, doc_data, state):
            faq = doc_data["data"]
            # Call original processor
            processed = self.data_processor._process_single_faq(faq)
            # Store vector_id in doc_data for state tracking
            doc_data["vector_id"] = f"faq_{doc_id}"
        
        return self.incremental.process_batch(docs, process_faq)
    
    def process_scenarios_incremental(self, scenarios: List[Dict]) -> Dict[str, Any]:
        """
        Process scenarios incrementally, skipping unchanged ones.
        
        Args:
            scenarios: List of scenario dicts with 'id', 'title', 'content'
        
        Returns:
            Details of what was processed
        """
        # Build doc map for change detection
        docs = {}
        for scenario in scenarios:
            doc_id = scenario.get("id", "")
            if not doc_id:
                continue
            
            content = f"{scenario.get('title', '')}\n{scenario.get('content', '')}"
            docs[doc_id] = {
                "content": content,
                "data": scenario,
                "source": "scenarios",
                "metadata": {
                    "difficulty": scenario.get("difficulty", "medium"),
                    "keywords": scenario.get("keywords", [])
                }
            }
        
        # Process only changed ones
        def process_scenario(doc_id, doc_data, state):
            scenario = doc_data["data"]
            # Call original processor
            processed = self.data_processor._process_single_scenario(scenario)
            doc_data["vector_id"] = f"scenario_{doc_id}"
        
        return self.incremental.process_batch(docs, process_scenario)
    
    def get_ingestion_status(self) -> Dict[str, Any]:
        """Get current ingestion status and statistics."""
        stats = self.incremental.get_stats()
        return {
            **stats,
            "summary": self.incremental.get_summary()
        }
