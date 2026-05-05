"""
Retrieves relevant documents from Pinecone vector DB
"""

from pinecone import Pinecone
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    def __init__(self):
        api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME", "f2-therapy-index")

        if not api_key:
            raise ValueError("PINECONE_API_KEY not configured")

        if not index_name:
            raise ValueError("PINECONE_INDEX_NAME not configured")

        try:
            self.pc = Pinecone(api_key=api_key)
            self.index = self.pc.Index(index_name)

            logger.info(f"Connected to Pinecone index: {index_name}")

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {str(e)}")
            raise

    def retrieve(self, query_vector: List[float], top_k: int = 5):
        """Retrieve top-k most relevant documents from vector DB."""
        if not query_vector:
            logger.warning("Empty query vector provided")
            return []

        try:
            results = self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True
            )

            # Safe access (avoids Pylance issues)
            matches = getattr(results, "matches", None)

            if matches is None:
                logger.warning(f"No matches found in result: {type(results)}")
                return []

            return matches

        except Exception as e:
            logger.error(f"Error querying Pinecone: {str(e)}")
            raise

    def get_context(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Get relevant context for the query."""
        try:
            matches = self.retrieve(query_vector, top_k=top_k)

            if not matches:
                return []

            context = []
            for match in matches:
                metadata = getattr(match, "metadata", {}) or {}

                context.append({
                    "id": getattr(match, "id", ""),
                    "content": metadata.get("content", ""),
                    "type": metadata.get("type", ""),
                    "score": getattr(match, "score", 0.0),
                })

            return context

        except Exception as e:
            logger.error(f"Error getting context: {str(e)}")
            raise

    def upsert_documents(
        self,
        vectors: List[List[float]],
        ids: List[str],
        metadata_list: List[Dict[str, Any]],
    ):
        """Upsert documents into Pinecone index."""
        if not (vectors and ids and metadata_list):
            logger.warning("Empty vectors, ids, or metadata provided")
            return

        if not (len(vectors) == len(ids) == len(metadata_list)):
            raise ValueError("Vectors, IDs, and metadata lists must have same length")

        try:
            # Correct format for Pinecone
            records = [
                (doc_id, vector, metadata)
                for vector, doc_id, metadata in zip(vectors, ids, metadata_list)
            ]

            self.index.upsert(vectors=records)

            logger.info(f"Upserted {len(records)} documents")

        except Exception as e:
            logger.error(f"Error upserting documents: {str(e)}")
            raise

    def delete_documents(self, ids: List[str]):
        """Delete documents from Pinecone index."""
        if not ids:
            logger.warning("Empty IDs list provided")
            return

        try:
            self.index.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents")

        except Exception as e:
            logger.error(f"Error deleting documents: {str(e)}")
            raise

    def get_index_stats(self):
        """Get statistics about the index."""
        try:
            stats = self.index.describe_index_stats()
            return stats

        except Exception as e:
            logger.error(f"Error getting index stats: {str(e)}")
            raise
