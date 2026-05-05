"""
Handles embedding generation using Google Gemini
"""

from functools import lru_cache
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import os
import logging

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_embeddings():
    """Initialize and return the embedding model."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set! Please configure it in your environment.")

    return GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-2",
        google_api_key=api_key
    )

def embed_text(text: str):
    """Convert text to embedding vector."""
    embeddings = get_embeddings()
    vector = embeddings.embed_query(text)
    return vector
