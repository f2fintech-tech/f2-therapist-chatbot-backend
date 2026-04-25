"""
Financial Therapist Chatbot with RAG (Retrieval-Augmented Generation) Pipeline
"""

import os
import logging
import json
from pathlib import Path
from google import genai
from pinecone import Pinecone
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()


class TherapyChatbot:
    """Financial Therapist Chatbot with RAG integration"""
    
    def __init__(self):
        """Initialize the chatbot with Gemini and Pinecone"""
        logger.info("Initializing TherapyChatbot...")
        
        # Validate Gemini API key
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key or not gemini_api_key.strip():
            raise ValueError(
                "GEMINI_API_KEY environment variable is not set or empty! "
                "Please set it in your .env file or environment."
            )
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=gemini_api_key)
        self.model_name = "gemini-3-flash-preview"
        
        # Validate Pinecone API key
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_api_key or not pinecone_api_key.strip():
            raise ValueError(
                "PINECONE_API_KEY environment variable is not set or empty! "
                "Please set it in your .env file or environment."
            )
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index = self.pc.Index("f2-therapy-index")
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt()
        
        logger.info("✓ TherapyChatbot initialized successfully")
    
    def _load_system_prompt(self):
        """Load the system prompt for the financial therapist"""
        prompt_path = Path("src/data/processed/system_prompt.md")
        
        if prompt_path.exists():
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Could not load system prompt: {e}")
        
        # Default system prompt
        return """You are a compassionate Financial Therapist for F2 Fintech.
Your core role:
- Empathetic listener who understands money stress
- Patient educator who explains without jargon
- Honest advisor who prioritizes customer wellbeing
- Practical problem-solver offering real solutions

Communication style:
- Warm and human (not corporate or robotic)
- Calm and reassuring, especially when customers are stressed
- Clear and simple (never condescending)
- Honest and transparent

Guidelines:
- Acknowledge emotion FIRST before addressing the question
- Use examples with real numbers
- Never say "Don't worry" (dismissive) or "It's simple" (makes them feel dumb)
- Never ignore the emotional content of their message
- Explain jargon: "EMI (Equated Monthly Installment - your fixed monthly payment)"
- Ask permission before giving long explanations: "Want me to explain how that works?"
- Never push products they don't need
- Never make promises you can't keep"""
    
    def _get_relevant_context(self, user_message, top_k=3):
        """Retrieve relevant knowledge base documents using RAG"""
        try:
            # Convert user message to embedding
            embed_result = self.client.models.embed_content(
                model="text-embedding-004",
                contents=user_message,
            )
            user_vector = embed_result.embeddings[0].values
            
            # Search Pinecone for relevant documents
            search_results = self.index.query(
                vector=user_vector,
                top_k=top_k,
                include_metadata=True
            )
            
            # Extract context from search results
            context_pieces = []
            if search_results.get('matches'):
                for match in search_results['matches']:
                    metadata = match.get('metadata', {})
                    content = metadata.get('content', '')
                    doc_type = metadata.get('type', 'unknown')
                    score = match.get('score', 0)
                    
                    if content:
                        context_pieces.append({
                            'content': content,
                            'type': doc_type,
                            'relevance_score': score
                        })
            
            logger.info(f"Retrieved {len(context_pieces)} relevant documents from knowledge base")
            return context_pieces
            
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []
    
    def _build_rag_prompt(self, user_message, context_pieces):
        """Build a prompt with RAG context for the model"""
        
        # Format context
        context_str = ""
        if context_pieces:
            context_str = "Relevant knowledge base information:\n"
            for i, piece in enumerate(context_pieces, 1):
                doc_type = piece.get('type', 'document')
                content = piece.get('content', '')[:300]  # Limit content length
                context_str += f"\n{i}. [{doc_type.upper()}] {content}\n"
        
        # Build the complete prompt
        rag_prompt = f"""{self.system_prompt}

=== RELEVANT KNOWLEDGE BASE ===
{context_str if context_str else "No specific knowledge base articles found. Use your general knowledge."}

=== USER MESSAGE ===
{user_message}

=== YOUR RESPONSE ===
"""
        
        return rag_prompt
    
    def chat(self, user_message, use_rag=True):
        """
        Chat with the financial therapist
        
        Args:
            user_message: The user's input message
            use_rag: Whether to use RAG (Retrieval-Augmented Generation)
        
        Returns:
            The therapist's response
        """
        logger.info(f"User: {user_message[:80]}...")
        
        try:
            context_pieces = []
            
            # Retrieve context if RAG is enabled
            if use_rag:
                context_pieces = self._get_relevant_context(user_message)
            
            # Build the prompt
            if context_pieces:
                prompt = self._build_rag_prompt(user_message, context_pieces)
            else:
                prompt = f"""{self.system_prompt}

User says: {user_message}"""
            
            # Generate response using Gemini
            logger.info(f"Generating response using {self.model_name}...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            
            if response and response.text:
                logger.info(f"Therapist: {response.text[:100]}...")
                return response.text
            else:
                logger.error("No response generated from model")
                return "I appreciate you reaching out, but I'm having trouble processing that right now. Could you try again?"
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"I'm sorry, I encountered an error while trying to help. Please try again in a moment."


def get_financial_therapy(user_message):
    """Legacy function for backward compatibility"""
    try:
        chatbot = TherapyChatbot()
        return chatbot.chat(user_message)
    except Exception as e:
        logger.error(f"Error in legacy function: {e}")
        return "I'm sorry, I encountered an error. Please try again."


if __name__ == "__main__":
    # Test the chatbot
    logging.basicConfig(level=logging.INFO)
    
    chatbot = TherapyChatbot()
    
    test_messages = [
        "I'm worried about my credit card debt",
        "How can I manage financial stress?",
        "What should I do if I missed an EMI payment?"
    ]
    
    print("\n" + "="*60)
    print("FINANCIAL THERAPIST CHATBOT - TEST SESSION")
    print("="*60)
    
    for msg in test_messages:
        print(f"\nUser: {msg}")
        response = chatbot.chat(msg)
        print(f"Therapist: {response}\n")
        print("-"*60)