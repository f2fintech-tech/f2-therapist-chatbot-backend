"""
Unit tests for incremental document ingestion tracking.
Tests IngestionState change detection, state persistence, and document status tracking.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from src.knowledge.ingestion_state import IngestionState


class TestIngestionState:
    """Test IngestionState change detection and state management."""
    
    @pytest.fixture
    def temp_state_file(self):
        """Create a temporary state file for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "test_state.json"
            yield state_file
    
    @pytest.fixture
    def state(self, temp_state_file):
        """Create a fresh IngestionState instance for testing."""
        return IngestionState(state_file=temp_state_file)
    
    def test_empty_state_on_init(self, state):
        """Test that new state is empty."""
        assert state.state["documents"] == {}
        assert state.state["last_sync"] is None
        assert state.state["stats"]["total_docs"] == 0
    
    def test_save_and_load_state(self, temp_state_file):
        """Test persisting and restoring state."""
        state1 = IngestionState(state_file=temp_state_file)
        state1.mark_embedded(
            "doc1",
            "Sample content",
            "faqs",
            "faq_1_abc123"
        )
        state1.save()
        
        # Create new instance from same file
        state2 = IngestionState(state_file=temp_state_file)
        assert "doc1" in state2.state["documents"]
        assert state2.state["documents"]["doc1"]["status"] == "embedded"
    
    def test_detect_new_document_as_changed(self, state):
        """Test that new documents are detected as changed."""
        is_changed = state.is_changed("new_doc", "content", "faqs")
        assert is_changed is True
    
    def test_detect_unchanged_document(self, state):
        """Test that unchanged documents are not detected as changed."""
        content = "FAQ content"
        
        # First mark as embedded
        state.mark_embedded("doc1", content, "faqs", "faq_1")
        
        # Check same content again
        is_changed = state.is_changed("doc1", content, "faqs")
        assert is_changed is False
    
    def test_detect_modified_content(self, state):
        """Test that modified content is detected as changed."""
        content1 = "Original content"
        content2 = "Modified content"
        
        state.mark_embedded("doc1", content1, "faqs", "faq_1")
        
        # Content changed
        is_changed = state.is_changed("doc1", content2, "faqs")
        assert is_changed is True
    
    def test_whitespace_normalization(self, state):
        """Test that whitespace differences don't trigger false changes."""
        content1 = "Content with spaces"
        content2 = "Content with spaces  \n\n"  # Extra whitespace
        
        state.mark_embedded("doc1", content1, "faqs", "faq_1")
        
        # Should be same after normalization
        is_changed = state.is_changed("doc1", content2, "faqs")
        assert is_changed is False
    
    def test_mark_embedded_updates_stats(self, state):
        """Test that marking documents as embedded updates statistics."""
        state.mark_embedded("doc1", "content1", "faqs", "faq_1")
        state.mark_embedded("doc2", "content2", "scenarios", "scen_2")
        
        stats = state.state["stats"]
        assert stats["total_docs"] == 2
        assert stats["embedded"] == 2
        assert stats["pending"] == 0
        assert stats["failed"] == 0
    
    def test_mark_failed_updates_stats(self, state):
        """Test that marking documents as failed updates statistics."""
        state.mark_embedded("doc1", "content1", "faqs", "faq_1")
        state.mark_failed("doc2", "Processing error", "faqs")
        
        stats = state.state["stats"]
        assert stats["total_docs"] == 2
        assert stats["embedded"] == 1
        assert stats["failed"] == 1
    
    def test_mark_processing_status(self, state):
        """Test marking document as being processed."""
        state.mark_processing("doc1", "faqs", {"key": "value"})
        
        record = state.state["documents"]["doc1"]
        assert record["status"] == "processing"
        assert record["source"] == "faqs"
        assert "started_at" in record
    
    def test_get_pending_docs(self, state):
        """Test retrieving list of pending documents."""
        state.mark_embedded("doc1", "content1", "faqs", "faq_1")
        state.mark_processing("doc2", "faqs")
        state.mark_failed("doc3", "Error", "faqs")
        
        pending = state.get_pending_docs()
        
        # Processing and failed are not completed, so they're pending
        assert "doc1" not in pending  # Embedded, not pending
        assert "doc2" in pending  # Processing, still pending
        assert "doc3" in pending  # Failed, still pending
    
    def test_get_changed_docs(self, state):
        """Test filtering documents to only those that changed."""
        docs = {
            "new_doc": {
                "content": "New content",
                "source": "faqs"
            },
            "existing_doc": {
                "content": "Existing content",
                "source": "faqs"
            }
        }
        
        # Mark one as embedded
        state.mark_embedded("existing_doc", "Existing content", "faqs", "faq_1")
        
        # Get changed docs
        changed = state.get_changed_docs(docs)
        
        assert "new_doc" in changed
        assert "existing_doc" not in changed
    
    def test_clear_processing_flags_on_resume(self, state):
        """Test that resume clears stale processing flags."""
        state.mark_processing("doc1", "faqs")
        state.mark_embedded("doc2", "content", "faqs", "faq_2")
        
        # Simulate crash - doc1 stuck in processing
        assert state.state["documents"]["doc1"]["status"] == "processing"
        
        # Resume clears processing flags
        state.clear_processing_flags()
        
        assert state.state["documents"]["doc1"]["status"] == "pending"
        assert state.state["documents"]["doc2"]["status"] == "embedded"
    
    def test_mark_sync_complete(self, state):
        """Test recording when sync completed."""
        before = datetime.utcnow().isoformat()
        state.mark_sync_complete()
        after = datetime.utcnow().isoformat()
        
        last_sync = state.state["last_sync"]
        assert last_sync is not None
        assert before <= last_sync <= after
    
    def test_get_doc_record(self, state):
        """Test retrieving a document record."""
        state.mark_embedded("doc1", "content", "faqs", "faq_1")
        
        record = state.get_doc_record("doc1")
        assert record is not None
        assert record["status"] == "embedded"
        assert record["source"] == "faqs"
    
    def test_get_stats(self, state):
        """Test getting ingestion statistics."""
        state.mark_embedded("doc1", "content1", "faqs", "faq_1")
        state.mark_embedded("doc2", "content2", "faqs", "faq_2")
        state.mark_failed("doc3", "Error", "faqs")
        state.mark_processing("doc4", "faqs")
        
        stats = state.get_stats()
        
        assert stats["stats"]["total_docs"] == 4
        assert stats["stats"]["embedded"] == 2
        assert stats["stats"]["failed"] == 1
        assert stats["stats"]["processing"] == 1
    
    def test_hash_consistency(self, state):
        """Test that same content always produces same hash."""
        content = "Test content"
        doc_id = "test_doc"
        
        # Mark embedded, get hash
        state.mark_embedded(doc_id, content, "faqs", "faq_1")
        record1 = state.get_doc_record(doc_id)
        hash1 = record1["hash"]
        
        # Clear and re-mark with same content
        state.state["documents"].clear()
        state.mark_embedded(doc_id, content, "faqs", "faq_1")
        record2 = state.get_doc_record(doc_id)
        hash2 = record2["hash"]
        
        assert hash1 == hash2
    
    def test_get_summary(self, state):
        """Test human-readable summary generation."""
        state.mark_embedded("doc1", "content", "faqs", "faq_1")
        state.mark_failed("doc2", "Error", "faqs")
        
        summary = state.get_summary()
        
        assert "Embedded: 1" in summary
        assert "Failed: 1" in summary
        assert "Total docs: 2" in summary
        assert "Last sync:" in summary


class TestIncrementalProcessorIntegration:
    """Integration tests for incremental processing workflow."""
    
    @pytest.fixture
    def temp_state_file(self):
        """Create a temporary state file for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "test_state.json"
            yield state_file
    
    @pytest.fixture
    def state(self, temp_state_file):
        """Create a fresh IngestionState instance for testing."""
        return IngestionState(state_file=temp_state_file)
    
    def test_batch_processing_workflow(self, state):
        """Test complete batch processing workflow."""
        from src.knowledge.incremental_processor import IncrementalProcessor
        
        processor = IncrementalProcessor(state.state_file)
        
        docs = {
            "doc1": {"content": "Content 1", "source": "faqs"},
            "doc2": {"content": "Content 2", "source": "faqs"},
        }
        
        # Mock processor function
        def mock_processor(doc_id, doc_data, state):
            pass
        
        # First run: all docs are new
        result1 = processor.process_batch(docs, mock_processor)
        assert result1["processed"] == 2
        assert result1["skipped"] == 0
        
        # Second run: all docs unchanged
        processor2 = IncrementalProcessor(state.state_file)
        result2 = processor2.process_batch(docs, mock_processor)
        assert result2["processed"] == 0
        assert result2["skipped"] == 2
    
    def test_resumable_batch_on_failure(self, state):
        """Test resuming batch processing after failure."""
        from src.knowledge.incremental_processor import IncrementalProcessor
        
        processor = IncrementalProcessor(state.state_file)
        
        docs = {
            "doc1": {"content": "Content 1", "source": "faqs"},
            "doc2": {"content": "Content 2", "source": "faqs"},
        }
        
        def failing_processor(doc_id, doc_data, state):
            if doc_id == "doc2":
                raise ValueError("Simulated failure")
        
        # First run fails on doc2
        processor.process_batch(docs, failing_processor)
        
        # Check state: doc1 embedded, doc2 failed
        assert processor.state.get_doc_record("doc1")["status"] == "embedded"
        assert processor.state.get_doc_record("doc2")["status"] == "failed"
        
        # Second run with resume_from_failed=True and working processor
        processor2 = IncrementalProcessor(state.state_file)
        
        def working_processor(doc_id, doc_data, state):
            pass
        
        result = processor2.process_batch(docs, working_processor, resume_from_failed=True)
        
        # doc2 should be retried now
        assert processor2.state.get_doc_record("doc2")["status"] == "embedded"
