"""
Financial Therapist Chatbot with RAG (Retrieval-Augmented Generation) Pipeline
"""

import os
import logging
import json
import re
import time
from pathlib import Path
from google import genai
from google.genai import types
from pinecone import Pinecone
from dotenv import load_dotenv
from src.utils.emotion_analyzer import analyze_emotion
from src.utils.conversation_state import build_conversation_state_guidance, infer_conversation_state
from src.knowledge.retriever import get_relevant_context

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
        # First, try to load fine-tuned prompt
        finetuned_path = Path("src/model/finetuned_system_prompt.txt")
        if finetuned_path.exists():
            try:
                with open(finetuned_path, 'r', encoding='utf-8') as f:
                    logger.info("✓ Loaded fine-tuned system prompt")
                    return f.read()
            except Exception as e:
                logger.warning(f"Could not load fine-tuned prompt: {e}")

        # Fallback to base prompt
        prompt_path = Path("src/data/processed/system_prompt.md")

        if prompt_path.exists():
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    logger.info("✓ Loaded base system prompt")
                    return f.read()
            except Exception as e:
                logger.warning(f"Could not load system prompt: {e}")

        # Default system prompt
        logger.warning("Using default system prompt - fine-tuned version recommended")
        return """You are a compassionate Financial Support Specialist for F2 Fintech. You are NOT a licensed therapist, counselor, or salesperson.
Your core role:
- Empathetic listener who understands money stress
- Patient educator who explains without jargon
- Honest advisor who prioritizes customer wellbeing
- Practical problem-solver offering real solutions

    Boundaries:
    - You can sound warm, human, and deeply attentive.
    - You cannot diagnose, treat, or provide mental health therapy.
    - You can acknowledge emotions, but you must not present yourself as a therapist.
    - If someone expresses self-harm, suicide, or another immediate safety crisis, stop financial advice and direct them to emergency or human support right away.
    - If the issue is emotional but not a safety crisis, encourage speaking with a licensed professional or trusted person while continuing with appropriate financial support.

Communication style:
    - Warm, human, and professional (not corporate or robotic)
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
- Never make promises you can't keep
- Never claim to be a licensed therapist or provide therapy
- Never diagnose mental health conditions
"""

    def _get_relevant_context(self, user_message, top_k=3):
        """Retrieve relevant knowledge base documents using RAG"""
        context_pieces = get_relevant_context(user_message, top_k=top_k)
        logger.info(f"Retrieved {len(context_pieces)} relevant documents from knowledge base")
        return context_pieces

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

    def _build_chat_prompt(self, user_message, conversation_history=None, context_pieces=None, state_guidance_text=None):
        """Build a chat prompt that includes optional conversation history."""
        history_block = ""
        if conversation_history:
            history_lines = []
            for turn in conversation_history[-6:]:
                role = turn.get("role", "user").capitalize()
                content = turn.get("content", "").strip()
                if content:
                    history_lines.append(f"{role}: {content}")
            if history_lines:
                history_block = "\nRecent conversation:\n" + "\n".join(history_lines) + "\n"

        rag_block = ""
        if context_pieces:
            rag_block = self._build_rag_prompt(user_message, context_pieces)
            return f"""{self.system_prompt}

{state_guidance_text or ""}

{history_block}
{rag_block}
"""

        return f"""{self.system_prompt}

    {state_guidance_text or ""}

    {history_block}
    User says: {user_message}"""
    def _build_structured_prompt(self, user_message, conversation_history=None, context_pieces=None, state_guidance_text=None):
        """Build prompt requesting JSON response."""
        base = self._build_chat_prompt(
            user_message,
            conversation_history,
            context_pieces,
            state_guidance_text=state_guidance_text,
        )
        return base + "\n\n=== RESPOND WITH JSON: {\"response\": \"...\", \"evaluation\": {\"relevance\": 0.8, \"groundedness\": 0.9, \"completeness\": 0.85}} ==="

    @staticmethod
    def _parse_json_response(text):
        """Parse JSON response with evaluation."""
        try:
            data = json.loads(text)
            e = data.get("evaluation", {})
            return {"response": data.get("response", ""), "relevance": max(0.0, min(1.0, float(e.get("relevance", 0.5)))), "groundedness": max(0.0, min(1.0, float(e.get("groundedness", 0.5)))), "completeness": max(0.0, min(1.0, float(e.get("completeness", 0.5)))), "parsed": True}
        except:
            return {"response": text[:300], "relevance": 0.5, "groundedness": 0.5, "completeness": 0.5, "parsed": False}


    @staticmethod
    def _retry_delay_from_error(error_message, default_delay=15.0):
        match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", error_message, re.IGNORECASE)
        return float(match.group(1)) if match else default_delay

    @staticmethod
    def _is_quota_exhausted(error_message):
        lowered = error_message.lower()
        return (
            "resource_exhausted" in lowered
            or "quota exceeded" in lowered
            or "exceeded your current quota" in lowered
            or "daily limit" in lowered
        )

    @staticmethod
    def _is_rate_limited(error_message):
        lowered = error_message.lower()
        return "429" in lowered or "too many requests" in lowered or "rate limit" in lowered

    def chat(self, user_message, use_rag=True, conversation_history=None, verbose=True, return_metadata=False):
        """
        Chat with the financial therapist

        Args:
            user_message: The user's input message
            use_rag: Whether to use RAG (Retrieval-Augmented Generation)
            conversation_history: Optional list of recent turns to preserve context
            verbose: Whether to log the user and therapist messages
            return_metadata: Whether to return response plus retrieval metadata

        Returns:
            The therapist's response (or metadata dict when return_metadata=True)
        """
        if verbose:
            logger.info(f"User: {user_message[:80]}...")

        try:
            # Analyze user emotion/mood
            conversation_depth = len(conversation_history) if conversation_history else 0
            mood_analysis = analyze_emotion(user_message, conversation_depth=conversation_depth)

            # Log mood analysis
            if verbose and mood_analysis:
                stress_level = mood_analysis.get('stress_level', 'unknown')
                emotional_state = mood_analysis.get('emotional_state', [])
                if stress_level != 'unknown' or emotional_state:
                    logger.info(f"  [Mood] Stress: {stress_level}, Emotional State: {', '.join(emotional_state) if emotional_state else 'neutral'}")

            context_pieces = []

            prior_turn_texts = []
            if conversation_history:
                prior_turn_texts = [
                    f"{turn.get('role', 'user').capitalize()}: {turn.get('content', '').strip()}"
                    for turn in conversation_history[-6:]
                    if turn.get("content", "").strip()
                ]

            conversation_state = infer_conversation_state(user_message, prior_turn_texts)
            state_guidance_text = build_conversation_state_guidance(conversation_state)

            # Retrieve context if RAG is enabled
            if use_rag:
                context_pieces = self._get_relevant_context(user_message)

            # Build the prompt (structured for metadata requests)
            if return_metadata:
                prompt = self._build_structured_prompt(
                    user_message,
                    conversation_history,
                    context_pieces,
                    state_guidance_text=state_guidance_text,
                )
            else:
                prompt = self._build_chat_prompt(
                    user_message,
                    conversation_history,
                    context_pieces,
                    state_guidance_text=state_guidance_text,
                )

            # Generate response using Gemini, with quota-aware retry handling
            logger.info(f"Generating response using {self.model_name}...")
            max_retries = 2
            response = None
            for attempt in range(1, max_retries + 1):
                try:
                    kw = {"model": self.model_name, "contents": prompt}
                    if return_metadata:
                        kw["config"] = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2, max_output_tokens=2048)
                    response = self.client.models.generate_content(**kw)
                    break
                except Exception as exc:
                    error_message = str(exc)
                    if not (self._is_quota_exhausted(error_message) or self._is_rate_limited(error_message)) or attempt == max_retries:
                        raise

                    retry_delay = self._retry_delay_from_error(error_message, default_delay=5.0)
                    retry_delay = min(retry_delay, 10.0)
                    retry_reason = "quota" if self._is_quota_exhausted(error_message) else "rate limit"
                    logger.warning(
                        f"Gemini {retry_reason} hit for chat message; waiting {retry_delay:.1f}s before retrying "
                        f"(attempt {attempt}/{max_retries})"
                    )
                    time.sleep(retry_delay)

            if response and response.text:
                response_text = response.text
                if return_metadata:
                    p = self._parse_json_response(response_text)
                    if verbose:
                        logger.info(f"Therapist: {p['response'][:100]}...")
                    return {
                        "response": p["response"],
                        "retrieved_chunks": [piece.get("content", "") for piece in context_pieces],
                        "mood_analysis": mood_analysis,
                        "evaluation": {
                            "relevance": p["relevance"],
                            "groundedness": p["groundedness"],
                            "completeness": p["completeness"],
                            "parsed": p["parsed"],
                        },
                        "conversation_state": conversation_state.to_dict(),
                    }
                if verbose:
                    logger.info(f"Therapist: {response_text[:100]}...")
                return response_text
            else:
                logger.error("No response generated from model")
                fallback = "I appreciate you reaching out, but I'm having trouble processing that right now. Could you try again?"
                if return_metadata:
                    return {"response": fallback, "retrieved_chunks": [piece.get("content", "") for piece in context_pieces], "mood_analysis": mood_analysis, "evaluation": {"relevance": 0.0, "groundedness": 0.0, "completeness": 0.0, "parsed": False}}
                return fallback

        except Exception as e:
            logger.error(f"Error in chat: {e}")
            fallback = "I'm sorry, I encountered an error while trying to help. Please try again in a moment."
            if return_metadata:
                return {"response": fallback, "retrieved_chunks": [], "mood_analysis": None, "evaluation": {"relevance": 0.0, "groundedness": 0.0, "completeness": 0.0, "parsed": False}, "conversation_state": conversation_state.to_dict()}
            return fallback


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
