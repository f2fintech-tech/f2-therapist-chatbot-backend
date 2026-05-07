"""
Track ingestion state: which documents have been processed, their hashes, and status.
Enables incremental updates and resumable pipelines.
"""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class IngestionState:
    """Manages document ingestion state with change detection and resumable processing."""
    
    # State file location
    DEFAULT_STATE_FILE = Path("src/data/processed/.ingestion_state.json")
    
    # Document status values
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_EMBEDDED = "embedded"
    STATUS_FAILED = "failed"
    STATUS_UPDATED = "updated"
    
    VALID_STATUSES = {STATUS_PENDING, STATUS_PROCESSING, STATUS_EMBEDDED, STATUS_FAILED, STATUS_UPDATED}
    
    def __init__(self, state_file: Optional[Path] = None):
        """
        Initialize ingestion state manager.
        
        Args:
            state_file: Path to state JSON file. Defaults to DEFAULT_STATE_FILE
        """
        self.state_file = state_file or self.DEFAULT_STATE_FILE
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from file or return empty state."""
        if not self.state_file.exists():
            logger.debug(f"State file {self.state_file} not found; starting fresh")
            return self._empty_state()
        
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            logger.info(f"Loaded ingestion state from {self.state_file}")
            return state
        except Exception as e:
            logger.warning(f"Failed to load state from {self.state_file}: {e}; starting fresh")
            return self._empty_state()
    
    def save(self):
        """Persist state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved ingestion state to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save ingestion state: {e}")
            raise
    
    @staticmethod
    def _empty_state() -> Dict[str, Any]:
        """Return empty initial state."""
        return {
            "last_sync": None,
            "documents": {},
            "stats": {
                "total_docs": 0,
                "embedded": 0,
                "failed": 0,
                "pending": 0,
                "updated": 0
            }
        }
    
    @staticmethod
    def _compute_hash(content: str) -> str:
        """Compute SHA256 hash of content."""
        normalized = content.strip().replace("\r\n", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    
    def is_changed(self, doc_id: str, content: str, source: str) -> bool:
        """
        Check if document has changed since last ingestion.
        
        Args:
            doc_id: Unique document identifier
            content: Document content (text to be embedded)
            source: Source collection (e.g., 'faqs', 'scenarios')
        
        Returns:
            True if document is new or content hash differs from stored hash
        """
        current_hash = self._compute_hash(content)
        
        if doc_id not in self.state["documents"]:
            return True
        
        stored_record = self.state["documents"][doc_id]
        stored_hash = stored_record.get("hash")
        
        return current_hash != stored_hash
    
    def get_pending_docs(self) -> List[str]:
        """
        Get list of document IDs pending processing (status != 'embedded').
        
        Returns:
            List of doc_ids that need processing
        """
        pending = []
        for doc_id, record in self.state["documents"].items():
            status = record.get("status", self.STATUS_PENDING)
            if status != self.STATUS_EMBEDDED:
                pending.append(doc_id)
        return pending
    
    def get_changed_docs(
        self,
        docs: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Filter documents to only those that have changed.
        
        Args:
            docs: Dict of {doc_id: {content, metadata, ...}}
        
        Returns:
            Filtered dict of only changed documents
        """
        changed = {}
        for doc_id, doc_data in docs.items():
            content = doc_data.get("content", "")
            source = doc_data.get("source", "unknown")
            
            if self.is_changed(doc_id, content, source):
                changed[doc_id] = doc_data
        
        return changed
    
    def mark_processing(self, doc_id: str, source: str, metadata: Optional[Dict] = None):
        """
        Mark document as currently being processed.
        
        Args:
            doc_id: Document ID
            source: Source collection name
            metadata: Optional metadata dict
        """
        self.state["documents"][doc_id] = {
            "status": self.STATUS_PROCESSING,
            "source": source,
            "started_at": datetime.utcnow().isoformat() + "Z",
            "metadata": metadata or {}
        }
    
    def mark_embedded(
        self,
        doc_id: str,
        content: str,
        source: str,
        vector_id: str,
        metadata: Optional[Dict] = None
    ):
        """
        Mark document as successfully embedded.
        
        Args:
            doc_id: Document ID
            content: Document content (used to compute hash)
            source: Source collection name
            vector_id: ID in vector database (Pinecone)
            metadata: Optional metadata dict
        """
        content_hash = self._compute_hash(content)
        
        self.state["documents"][doc_id] = {
            "hash": content_hash,
            "status": self.STATUS_EMBEDDED,
            "vector_id": vector_id,
            "source": source,
            "last_embedded": datetime.utcnow().isoformat() + "Z",
            "metadata": metadata or {}
        }
        
        # Update stats
        self._update_stats()
    
    def mark_failed(self, doc_id: str, error: str, source: str):
        """
        Mark document as failed during processing.
        
        Args:
            doc_id: Document ID
            error: Error message or reason for failure
            source: Source collection name
        """
        self.state["documents"][doc_id] = {
            "status": self.STATUS_FAILED,
            "source": source,
            "last_error": error,
            "failed_at": datetime.utcnow().isoformat() + "Z",
            "metadata": {}
        }
        
        # Update stats
        self._update_stats()
    
    def mark_updated(self, doc_id: str, source: str):
        """
        Mark document as updated (changed content, needs re-embedding).
        
        Args:
            doc_id: Document ID
            source: Source collection name
        """
        self.state["documents"][doc_id]["status"] = self.STATUS_UPDATED
        self._update_stats()
    
    def mark_sync_complete(self):
        """Mark the current sync as complete."""
        self.state["last_sync"] = datetime.utcnow().isoformat() + "Z"
        self._update_stats()
    
    def _update_stats(self):
        """Recompute statistics from current state."""
        docs = self.state["documents"]
        stats = {
            "total_docs": len(docs),
            "embedded": sum(1 for d in docs.values() if d.get("status") == self.STATUS_EMBEDDED),
            "failed": sum(1 for d in docs.values() if d.get("status") == self.STATUS_FAILED),
            "pending": sum(1 for d in docs.values() if d.get("status") == self.STATUS_PENDING),
            "updated": sum(1 for d in docs.values() if d.get("status") == self.STATUS_UPDATED),
            "processing": sum(1 for d in docs.values() if d.get("status") == self.STATUS_PROCESSING),
        }
        self.state["stats"] = stats
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current ingestion statistics."""
        self._update_stats()
        return {
            "last_sync": self.state.get("last_sync"),
            "stats": self.state["stats"],
            "documents": len(self.state["documents"])
        }
    
    def get_doc_record(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get stored record for a document."""
        return self.state["documents"].get(doc_id)
    
    def clear_processing_flags(self):
        """
        Reset any 'processing' status to 'pending' (for resuming failed runs).
        Useful when pipeline crashed mid-processing.
        """
        for doc_id, record in self.state["documents"].items():
            if record.get("status") == self.STATUS_PROCESSING:
                record["status"] = self.STATUS_PENDING
                logger.info(f"Reset {doc_id} from processing to pending (resuming)")
        
        self._update_stats()
    
    def get_summary(self) -> str:
        """Get human-readable summary of ingestion state."""
        self._update_stats()
        stats = self.state["stats"]
        last_sync = self.state.get("last_sync", "never")
        
        summary = (
            f"Ingestion State Summary:\n"
            f"  Last sync: {last_sync}\n"
            f"  Total docs: {stats['total_docs']}\n"
            f"  Embedded: {stats['embedded']}\n"
            f"  Updated (needs re-embed): {stats['updated']}\n"
            f"  Pending: {stats['pending']}\n"
            f"  Failed: {stats['failed']}\n"
            f"  Processing: {stats['processing']}"
        )
        return summary
