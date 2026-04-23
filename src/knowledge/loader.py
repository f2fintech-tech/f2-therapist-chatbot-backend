"""
Loads knowledge base documents into Pinecone
"""

import json
import logging
from pathlib import Path
from .embedder import embed_text
from pinecone import Pinecone
import os

logger = logging.getLogger(__name__)

class KnowledgeLoader:
    def __init__(self):
        api_key = os.getenv("export PINECONE_API_KEY="pcsk_66p3nV_DsKrE4Kx7we6oC6P6jgiYb6djJFJSDzAVtfhyCWsPUWweXA3FrWNBZbDenzeyb2"")
        index_name = "f2-therapy-index"
        
        if not api_key:
            raise ValueError("PINECONE_API_KEY not configured")
        
        self.client = Pinecone(api_key=api_key)
        self.index = self.client.Index(index_name)
    
    def load_scenarios(self):
        """Load scenarios from JSON into vector DB."""
        scenarios_path = Path("src/data/processed/scenarios.json")
        
        if not scenarios_path.exists():
            logger.warning(f"Processed scenarios not found at {scenarios_path}")
            return
        
        with open(scenarios_path, 'r', encoding='utf-8') as f:
            scenarios = json.load(f)
        
        vectors = []
        for scenario in scenarios:
            content = f"{scenario['title']}: {scenario['content']}"
            vector = embed_text(content)
            
            vectors.append({
                'id': scenario['id'],
                'values': vector,
                'metadata': {
                    'content': content,
                    'type': 'scenario',
                    'category': scenario.get('category'),
                    'severity': scenario.get('severity')
                }
            })
        
        self.index.upsert(vectors=vectors)
        logger.info(f"Loaded {len(vectors)} scenarios into Pinecone")
    
    def load_faqs(self):
        """Load FAQs from JSON into vector DB."""
        faqs_path = Path("src/data/processed/faqs.json")
        
        if not faqs_path.exists():
            logger.warning(f"Processed FAQs not found at {faqs_path}")
            return
        
        with open(faqs_path, 'r', encoding='utf-8') as f:
            faqs = json.load(f)
        
        vectors = []
        for faq in faqs:
            content = f"Q: {faq['question']}\nA: {faq['answer']}"
            vector = embed_text(content)
            
            vectors.append({
                'id': faq['id'],
                'values': vector,
                'metadata': {
                    'content': content,
                    'type': 'faq',
                    'category': faq.get('category'),
                    'tags': faq.get('tags', [])
                }
            })
        
        self.index.upsert(vectors=vectors)
        logger.info(f"Loaded {len(vectors)} FAQs into Pinecone")
    
    def load_all(self):
        """Load all knowledge base documents."""
        logger.info("Loading knowledge base into Pinecone...")
        self.load_scenarios()
        self.load_faqs()
        logger.info("Knowledge base loaded successfully!")

if __name__ == "__main__":
    loader = KnowledgeLoader()
    loader.load_all()