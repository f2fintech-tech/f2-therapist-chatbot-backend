"""
Retrieves relevant documents from Pinecone vector DB
"""

from pinecone import Pinecone
import os
import logging

logger = logging.getLogger(__name__)

class KnowledgeRetriever:
    def __init__(self):
        api_key = os.getenv("export PINECONE_API_KEY="pcsk_66p3nV_DsKrE4Kx7we6oC6P6jgiYb6djJFJSDzAVtfhyCWsPUWweXA3FrWNBZbDenzeyb2"")
        index_name = "f2-therapy-index"
        
        if not api_key:
            logger.error("PINECO")
            raise ValueError("PINECONE_API_KEY not configured")
        
        self.client = Pinecone(api_key=api_key)
        self.index = self.client.Index(index_name)
    
    def retrieve(self, query_vector: list, top_k: int = 5):
        """Retrieve top-k most relevant documents from vector DB."""
        results = self.index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True
        )
        return results['matches']
    
    def get_context(self, query_vector: list):
        """Get relevant context for the query."""
        matches = self.retrieve(query_vector, top_k=5)
        
        context = []
        for match in matches:
            metadata = match.get('metadata', {})
            context.append({
                'content': metadata.get('content', ''),
                'type': metadata.get('type', ''),
                'score': match['score']
            })
        
        return context