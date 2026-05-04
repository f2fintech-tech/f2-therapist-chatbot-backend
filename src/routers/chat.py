"""
Chat router with message handling and conversation persistence.
Integrates with Google Gemini 3 flash preview via LangChain and Knowledge Base (RAG).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import os
import logging
import uuid
import re
import time
import json
import threading

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from src.models import (
    get_db, Conversation, ConversationMessage, MessageRole, get_or_create_user
)
from src.utils.validators import (
    sanitize_message, sanitize_string, validate_and_sanitize,
    ValidatedMessage, ValidatedConversation, UUID_PATTERN,
    MAX_MESSAGE_LENGTH, MIN_MESSAGE_LENGTH
)
from utils.emotion_analyzer import analyze_emotion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

# ==================== Constants ====================
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
MAX_MESSAGE_LENGTH = 5000
MIN_MESSAGE_LENGTH = 1
CONTEXT_WINDOW_MESSAGES = 10
MOOD_ADAPTATION_ENV = "ENABLE_MOOD_RESPONSE_ADAPTATION"
MOOD_SNAPSHOT_ANALYZER_VERSION = "emotion_analyzer_v1"
MOOD_SNAPSHOT_RESULTS_PATH = Path(__file__).resolve().parents[1] / "model" / "model_test_results.json"

_mood_snapshot_lock = threading.Lock()

# ==================== Pydantic Models ====================
class ChatRequest(BaseModel):
    """Chat request model with validation."""
    message: str = Field(..., min_length=MIN_MESSAGE_LENGTH, max_length=MAX_MESSAGE_LENGTH, description="User message")
    user_id: str = Field(..., min_length=1, max_length=36, description="Unique user identifier")
    conversation_id: str | None = Field(None, min_length=36, max_length=36, description="Optional conversation ID")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user_id is a valid UUID format."""
        if not UUID_PATTERN.match(v):
            raise ValueError("Invalid user_id format. Must be a valid UUID.")
        return v.lower()
    
    @validator('message')
    def validate_message(cls, v):
        """Sanitize and validate message."""
        try:
            return sanitize_message(v)
        except ValueError as e:
            raise ValueError(f"Invalid message: {str(e)}")
    
    @validator('conversation_id', pre=True, always=True)
    def validate_conversation_id(cls, v):
        """Validate conversation_id if provided."""
        if v is None:
            return None
        if not UUID_PATTERN.match(v):
            raise ValueError("Invalid conversation_id format. Must be a valid UUID.")
        return v.lower()

class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    user_id: str
    conversation_id: str
    message_id: str
    timestamp: datetime
    mood: dict | None = Field(None, description="User's mood and emotion indicators")


class MoodAnalysisRequest(BaseModel):
    """Request model for mood analysis endpoint."""
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    conversation_depth: int = Field(0, ge=0, le=100)


class MoodAnalysisResponse(BaseModel):
    """Response model for mood analysis."""
    message: str
    stress_level: str
    stress_confidence: float
    indicators: dict
    confidence_scores: dict
    conversation_phase: str
    overall_confidence: float
    detected_keywords: list | None = None

# ==================== LLM Configuration ====================
@lru_cache(maxsize=1)
def get_llm():
    """Initialize and return the Google Gemini 3 flash preview LLM instance."""

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables")
        raise ValueError("GEMINI_API_KEY not configured")

    return ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        temperature=0.7,
        max_output_tokens=3072,
        google_api_key=api_key
    )

def get_financial_therapy_prompt():
    """Create and return the financial therapy system prompt."""
    system_message = """**# WHO YOU ARE**
You are a compassionate Financial Therapist working at F2 Fintech. You are NOT a salesperson. 
You are a trusted advisor who genuinely cares about people's financial and emotional wellbeing.

Your core identity:
- Empathetic listener who understands money stress
- Patient educator who explains without jargon
- Honest advisor who prioritizes customer wellbeing over sales
- Non-judgmental supporter who validates feelings
- Practical problem-solver who offers real solutions

**# YOUR PURPOSE**
You listen to them like an actual therapist, offer emotional support, and then help them understand their financial situation and options.
You do not judge them for their past financial decisions or current situation. 
You meet them where they are and help them move forward in a way that makes sense for them.
Help people navigate their financial journey with both emotional support and practical guidance. 
Many customers come to you stressed, confused, or ashamed about their financial situation. 
Your job is to make them feel heard, understood, and empowered.

**# HOW YOU COMMUNICATE**

**Tone:**
- Warm and human (not corporate or robotic)
- Calm and reassuring (especially when they're stressed)
- Clear and simple (never condescending)
- Honest and transparent (even when it's not what they want to hear)

**Language Guidelines:**
- Use "you" and "I" (conversational, not "the customer" or "we at F2")
- Explain jargon immediately: "EMI (Equated Monthly Installment - your fixed monthly payment)"
- Use examples with real numbers: "For example, if you borrow ₹1 lakh..."
- Break complex topics into small pieces
- Ask permission before giving long explanations: "Want me to explain how that works?"

**Structure:**
- Acknowledge emotion FIRST: "I can hear the worry in your question..."
- Then address the question
- Offer next step at the end

**What you NEVER do:**
- Never use phrases like "Don't worry" (dismissive)
- Never say "It's simple" or "Obviously" (makes them feel dumb)
- Never push products they don't need
- Never ignore emotional content of their message
- Never use complex financial jargon without explanation
- Never make promises you can't keep ("You'll definitely be approved")

**# WHAT YOU KNOW**

**About F2 Fintech Products:**
- Personal loans: ₹50,000 to ₹25,00,000
- Professional loans: ₹1,00,000 to ₹50,00,000
- Interest rates: 10.99% to 24% (reducing balance, based on credit profile)
- Tenure: 12 to 60 months
- Processing fees: 2% of loan amount
- Zero prepayment charges
- Approval time: 24-48 hours
- Disbursal: 2-3 working days after approval

**Financial Concepts You Can Explain:**
- EMI calculation and what affects it
- Interest rates (reducing vs flat, fixed vs floating)
- Credit scores and how they work
- Debt consolidation pros and cons
- Loan eligibility criteria
- Impact of tenure on total interest paid

**# HOW YOU HANDLE DIFFERENT SITUATIONS**

**When someone is anxious:**
- Validate their feeling: "It's completely normal to feel nervous about this"
- Break down the scary thing into manageable pieces
- Give them control: "Would you like to see the numbers first before deciding?"
- Reassure with facts, not empty promises

**When someone doesn't understand:**
- Never make them feel stupid
- Use analogies: "Think of it like..."
- Give concrete examples with numbers
- Check understanding: "Does that make sense, or should I explain it differently?"

**When someone is in crisis:**
- Acknowledge urgency: "I understand you need help quickly"
- Be realistic about timelines
- Offer alternative solutions if you can't help immediately
- Prioritize practical next steps

**When someone doesn't trust you:**
- Don't get defensive
- Prove trustworthiness with transparency
- Show, don't tell: Give them exact numbers and breakdowns
- Acknowledge past bad experiences: "I understand you've been burned before"

**When someone is comparing options:**
- Don't badmouth competitors
- Give them objective criteria to compare
- Be honest about F2's strengths AND limitations
- Empower them to make informed choice

**When you don't know something:**
- Be honest: "That's a great question. I don't have that specific information right now"
- Offer to find out: "Let me check and get back to you"
- Never make up information

**# YOUR GOALS (IN ORDER OF PRIORITY)**

1. **Make them feel heard and understood** - Emotional support comes first
2. **Educate them** - Help them make informed decisions
3. **Solve their problem** - Practical solutions
4. **Guide them to right product** - Only if it genuinely helps them
5. **Move them forward** - Next step, even if not a loan

Remember: Your success is not measured by how many loans you give out, but by how many 
people you genuinely help - even if that means telling them NOT to take a loan.

**# CONVERSATION FLOW**

**Opening:**
- Greet warmly
- Ask what brings them here today
- Listen actively

**Discovery:**
- Understand their situation (financial + emotional)
- Ask clarifying questions
- Validate their feelings

**Education:**
- Explain relevant concepts
- Use their specific numbers in examples
- Check understanding

**Solution:**
- Offer options (not just one)
- Show pros and cons honestly
- Let them decide

**Next Step:**
- Clear, specific action
- Timeline expectations
- Support available

Remember: This is a conversation with a real person facing real stress. Treat them with 
the dignity, respect, and patience you'd want if you were in their shoes."""
    
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "{user_message}")
    ])


def _retry_delay_from_error(error_message: str, default_delay: float = 5.0) -> float:
    """Extract retry-after seconds from provider error text when available."""
    match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", error_message, re.IGNORECASE)
    return float(match.group(1)) if match else default_delay


def _is_quota_exhausted(error_message: str) -> bool:
    lowered = error_message.lower()
    return (
        "resource_exhausted" in lowered
        or "quota exceeded" in lowered
        or "exceeded your current quota" in lowered
        or "daily limit" in lowered
    )


def _is_rate_limited(error_message: str) -> bool:
    lowered = error_message.lower()
    return "429" in lowered or "too many requests" in lowered or "rate limit" in lowered


def _is_feature_enabled(env_var: str, default: str = "true") -> bool:
    """Read boolean-like env flags safely."""
    value = os.getenv(env_var, default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_mood_adaptation_guidance(mood_analysis: dict | None) -> str:
    """Build concise response-style instructions from detected mood signals."""
    if not mood_analysis:
        return ""

    stress = mood_analysis.get("stress_level")
    indicators = mood_analysis.get("indicators", {})
    emotional_state = indicators.get("emotional_state")
    urgency = indicators.get("financial_urgency")
    willingness = indicators.get("willingness_to_learn")
    openness = indicators.get("openness_to_solutions")
    confidence = mood_analysis.get("overall_confidence", 0.0)

    # Avoid over-steering when analysis confidence is weak.
    if confidence < 0.35:
        return ""

    guidance = ["Mood-based response adaptation:"]

    if stress == "high":
        guidance.append("- Keep response short (about 70-140 words) and calming.")
        guidance.append("- Acknowledge emotion first, then provide one immediate concrete step.")
    elif stress == "moderate":
        guidance.append("- Keep response medium length (about 100-180 words) with empathy and practical guidance.")
        guidance.append("- Provide one or two clear next steps.")
    elif stress == "low":
        guidance.append("- User appears calmer; you may provide deeper but still concise explanation (about 140-240 words).")

    if emotional_state == "confused":
        guidance.append("- Use simple language and one concrete numeric example.")
    elif emotional_state == "shameful":
        guidance.append("- Normalize their feelings and avoid any judgmental framing.")
    elif emotional_state == "hopeless":
        guidance.append("- Emphasize small achievable progress and user agency.")
    elif emotional_state == "defensive":
        guidance.append("- Use non-confrontational language and ask one clarifying question.")

    if urgency == "crisis":
        guidance.append("- Prioritize immediate timeline-focused steps for the next 24-72 hours.")
    elif urgency == "urgent":
        guidance.append("- Prioritize a near-term plan for this week.")

    if willingness == "high":
        guidance.append("- User is willing to learn: add a brief explanation and ask if they want more detail.")
    elif willingness == "low":
        guidance.append("- Minimize theory; focus on direct actions.")

    if openness == "closed":
        guidance.append("- Do not push product or funding options; focus on supportive planning.")
    elif openness == "ready":
        guidance.append("- Offer actionable options with pros/cons, while staying non-salesy.")

    return "\n".join(guidance)


def _stress_level_to_score(stress_level: str | None) -> int | None:
    """Map categorical stress to numeric score for trend analysis."""
    mapping = {
        "unknown": 0,
        "low": 1,
        "moderate": 2,
        "high": 3,
    }
    return mapping.get((stress_level or "").lower())


def _load_results_file(path: Path) -> dict:
    """Load persisted results JSON safely, falling back to an empty dict."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Failed to load mood snapshot store %s: %s", path, str(exc))
        return {}


def _save_results_file(path: Path, data: dict) -> None:
    """Write results JSON atomically to avoid partial writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def _previous_stress_for_conversation(snapshots: list, conversation_id: str) -> str | None:
    """Get previous stress level for the same conversation from existing snapshots."""
    for item in reversed(snapshots):
        if item.get("conversation_id") == conversation_id:
            return item.get("stress_level")
    return None


def persist_mood_snapshot(
    *,
    user_id: str,
    conversation_id: str,
    user_message_id: str,
    assistant_message_id: str,
    user_message: str,
    assistant_response: str,
    mood_analysis: dict,
    conversation_depth: int,
    model_name: str,
    file_path: Path = MOOD_SNAPSHOT_RESULTS_PATH,
) -> None:
    """Persist a mood snapshot to JSON for analytics/auditing without DB tables."""
    stress_level = mood_analysis.get("stress_level")

    with _mood_snapshot_lock:
        data = _load_results_file(file_path)
        snapshots = data.setdefault("mood_snapshots", [])

        previous_stress = _previous_stress_for_conversation(snapshots, conversation_id)
        current_score = _stress_level_to_score(stress_level)
        previous_score = _stress_level_to_score(previous_stress)
        stress_delta = None
        if current_score is not None and previous_score is not None:
            stress_delta = current_score - previous_score

        snapshot = {
            "timestamp": time.time(),
            "analyzer_version": MOOD_SNAPSHOT_ANALYZER_VERSION,
            "model": model_name,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "conversation_depth": conversation_depth,
            "message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
            "user_message": user_message,
            "assistant_response": assistant_response,
            "stress_level": stress_level,
            "stress_score": current_score,
            "stress_trend": {
                "previous_stress_level": previous_stress,
                "previous_stress_score": previous_score,
                "delta": stress_delta,
            },
            "indicators": mood_analysis.get("indicators", {}),
            "confidence_scores": mood_analysis.get("confidence_scores", {}),
            "stress_confidence": mood_analysis.get("stress_confidence"),
            "overall_confidence": mood_analysis.get("overall_confidence"),
            "conversation_phase": mood_analysis.get("conversation_phase"),
            "detected_keywords": mood_analysis.get("detected_keywords", []),
        }

        snapshots.append(snapshot)
        data["latest_mood_snapshot"] = snapshot
        _save_results_file(file_path, data)

# ==================== Helper Functions ====================
def get_or_create_conversation(db: Session, user_id: str, conversation_id: str | None = None):
    """Get existing conversation or create a new one."""
    if conversation_id:
        if not UUID_PATTERN.match(conversation_id):
            logger.warning(f"Invalid conversation_id format: {conversation_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation_id format"
            )
        
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            logger.warning(f"Conversation not found: {conversation_id} for user: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or unauthorized"
            )
        return conversation
    else:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=None
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        logger.info(f"New conversation created: {conversation.id} for user: {user_id}")
        return conversation

def save_message(db: Session, conversation_id: str, role: MessageRole, content: str):
    """Save a message to the database."""
    # Validate and sanitize content
    try:
        validated_content = sanitize_message(content)
    except ValueError as e:
        logger.error(f"Message validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid message content: {str(e)}"
        )
    
    message = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=validated_content
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message

def get_conversation_context(db: Session, conversation_id: str, limit: int = 10):
    """Get recent conversation messages for context (last N messages)."""
    messages = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation_id
    ).order_by(ConversationMessage.created_at.desc()).limit(limit).all()
    
    return list(reversed(messages))

def format_conversation_context(messages: list[ConversationMessage]) -> str:
    """Format recent conversation turns into plain text for prompt context."""
    if not messages:
        return ""

    history_lines = []
    for msg in messages:
        role = "User" if msg.role == MessageRole.USER else "Assistant"
        content = (msg.content or "").strip()
        if not content:
            continue
        history_lines.append(f"{role}: {content}")

    if not history_lines:
        return ""

    return "\n".join(history_lines)

# ==================== Routes ====================
@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Main chat endpoint for the financial therapy chatbot.
    
    Accepts a user message, retrieves relevant knowledge from the knowledge base,
    manages conversation context, and returns an AI response grounded in your data.
    Automatically persists all messages to the database.
    Input is validated and sanitized for security.
    
    Args:
        request: ChatRequest containing user message and optional conversation ID
        db: Database session
        
    Returns:
        ChatResponse with the AI's response and conversation details
        
    Raises:
        HTTPException: For validation errors, missing API key, or database issues
    """
    try:
        request_start = time.perf_counter()

        # Ensure user exists
        user = get_or_create_user(db, request.user_id)
        logger.info(f"User authenticated: {request.user_id}")
        
        # Get or create conversation
        conversation = get_or_create_conversation(
            db, request.user_id, request.conversation_id
        )
        
        # Save user message (already validated by ChatRequest model)
        user_message_obj = save_message(
            db, conversation.id, MessageRole.USER, request.message
        )
        logger.info(f"User message saved: {user_message_obj.id}")
        
        # Analyze user's mood and emotional state
        conversation_depth = conversation.message_count // 2  # Each exchange = 2 messages
        mood_analysis = analyze_emotion(request.message, conversation_depth)
        logger.info(f"Mood analysis: stress={mood_analysis.get('stress_level')}, confidence={mood_analysis.get('stress_confidence')}")

        mood_adaptation_enabled = _is_feature_enabled(MOOD_ADAPTATION_ENV, default="true")
        mood_guidance_text = ""
        if mood_adaptation_enabled:
            mood_guidance_text = _build_mood_adaptation_guidance(mood_analysis)
            if mood_guidance_text:
                logger.info("Mood adaptation guidance applied to prompt")
        else:
            logger.info("Mood adaptation disabled via env var %s", MOOD_ADAPTATION_ENV)
        
        # Get conversation context for LLM
        context_start = time.perf_counter()
        context_messages = get_conversation_context(
            db,
            conversation.id,
            limit=CONTEXT_WINDOW_MESSAGES
        )
        # Exclude the current user message to avoid duplicate content in the same prompt.
        prior_context_messages = context_messages[:-1]
        conversation_context_text = format_conversation_context(prior_context_messages)
        
        # ==================== NEW: RAG Integration ====================
        # Retrieve relevant knowledge from Pinecone
        logger.info(f"Retrieving knowledge base context for query: {request.message}")
        
        context_text = ""
        knowledge_context = []
        
        try:
            from src.knowledge.embedder import embed_text
            from src.knowledge.retriever import KnowledgeRetriever
            
            # Convert user message to embedding
            query_vector = embed_text(request.message)
            logger.debug("User message converted to embedding vector")
            
            # Search Pinecone for relevant documents
            retriever = KnowledgeRetriever()
            knowledge_context = retriever.get_context(query_vector)
            logger.info(f"Retrieved {len(knowledge_context)} relevant knowledge documents")
            
            # Build context string from retrieved documents
            if knowledge_context:
                context_text = "📚 **Relevant Knowledge Base**:\n"
                for idx, doc in enumerate(knowledge_context, 1):
                    content_preview = doc['content'][:300] if doc['content'] else "No content"
                    context_text += f"\n{idx}. {content_preview}...\n"
                context_text += "\n---\n\n"
                logger.info(f"Built knowledge context with {len(knowledge_context)} documents")
            else:
                logger.info("No relevant knowledge documents found in vector DB")

            logger.info(
                "RAG retrieval completed in %.2fs",
                time.perf_counter() - context_start,
            )
        
        except Exception as e:
            logger.warning(f"Knowledge base retrieval failed: {str(e)}. Continuing without context.")
            context_text = ""
            knowledge_context = []
        
        # ==================== Build Enhanced Message ====================
        # Combine prior conversation, knowledge context, and current user message.
        enhanced_message_parts = []
        if conversation_context_text:
            enhanced_message_parts.append(
                "Recent Conversation Context:\n"
                f"{conversation_context_text}\n"
                "\nUse this context to avoid asking the user to repeat details they already shared.\n"
            )

        if context_text:
            enhanced_message_parts.append(context_text)

        if mood_guidance_text:
            enhanced_message_parts.append(mood_guidance_text)

        enhanced_message_parts.append(f"**User's Question:**\n{request.message}")
        enhanced_message = "\n".join(enhanced_message_parts)
        
        logger.info(f"Enhanced message length: {len(enhanced_message)} characters")
        
        # Initialize LLM and prompt
        llm = get_llm()
        prompt = get_financial_therapy_prompt()
        
        # Create the chain and get response (with knowledge context)
        chain = prompt | llm
        generation_start = time.perf_counter()
        max_retries = 2
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                response = chain.invoke({"user_message": enhanced_message})
                break
            except Exception as exc:
                error_message = str(exc)
                is_quota = _is_quota_exhausted(error_message)
                is_rate_limit = _is_rate_limited(error_message)

                # Retry only for temporary capacity/rate pressure and stop on final attempt.
                if not (is_quota or is_rate_limit) or attempt == max_retries:
                    raise

                retry_delay = _retry_delay_from_error(error_message, default_delay=5.0)
                retry_delay = min(retry_delay, 10.0)
                retry_reason = "quota" if is_quota else "rate limit"
                logger.warning(
                    "Gemini %s hit for chat route; waiting %.1fs before retrying (attempt %d/%d)",
                    retry_reason,
                    retry_delay,
                    attempt,
                    max_retries,
                )
                time.sleep(retry_delay)

        if response is None:
            raise RuntimeError("No response generated from model")

        logger.info("Model generation completed in %.2fs", time.perf_counter() - generation_start)

        # Ensure assistant response is a string before saving/persisting
        assistant_text = None
        try:
            assistant_text = response.content if isinstance(response.content, str) else str(response.content)
        except Exception:
            assistant_text = str(response)

        # Save assistant message
        assistant_message_obj = save_message(
            db, conversation.id, MessageRole.ASSISTANT, assistant_text
        )
        logger.info(f"Assistant message saved: {assistant_message_obj.id}")

        persist_mood_snapshot(
            user_id=request.user_id,
            conversation_id=conversation.id,
            user_message_id=user_message_obj.id,
            assistant_message_id=assistant_message_obj.id,
            user_message=request.message,
            assistant_response=assistant_text,
            mood_analysis=mood_analysis,
            conversation_depth=conversation_depth,
            model_name="gemini-3-flash-preview",
        )
        logger.info("Mood snapshot persisted for conversation %s", conversation.id)
        
        # Update conversation metadata
        conversation.message_count += 2
        conversation.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Chat exchange completed for user {request.user_id} in conversation {conversation.id}")
        logger.info(f"Response length: {len(assistant_text)} characters")
        logger.info("Total chat request completed in %.2fs", time.perf_counter() - request_start)
        
        return ChatResponse(
            response=assistant_text,
            user_id=request.user_id,
            conversation_id=conversation.id,
            message_id=assistant_message_obj.id,
            timestamp=datetime.utcnow(),
            mood={
                "stress_level": mood_analysis.get("stress_level"),
                "emotional_state": mood_analysis.get("indicators", {}).get("emotional_state"),
                "financial_urgency": mood_analysis.get("indicators", {}).get("financial_urgency"),
                "willingness_to_learn": mood_analysis.get("indicators", {}).get("willingness_to_learn"),
                "openness_to_solutions": mood_analysis.get("indicators", {}).get("openness_to_solutions"),
                "stress_confidence": mood_analysis.get("stress_confidence"),
                "overall_confidence": mood_analysis.get("overall_confidence"),
            }
        )
    
    except ValueError as e:
        logger.error(f"Configuration error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API configuration error. Please contact support."
        )
    
    except HTTPException:
        raise

    except Exception as e:
        error_message = str(e)
        if _is_quota_exhausted(error_message):
            logger.error(f"Quota exhausted in chat endpoint: {error_message}")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Model usage quota reached. Please try again later.",
            )
        if _is_rate_limited(error_message):
            logger.warning(f"Rate-limited in chat endpoint: {error_message}")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Model is temporarily rate-limited. Please retry shortly.",
            )
    
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request"
        )


# ==================== Emotion Analysis Endpoint ====================
@router.post("/analyze-mood", response_model=MoodAnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_user_mood(request: MoodAnalysisRequest):
    """
    Analyze user message for emotional state and mood indicators.
    
    Returns stress level, emotional state, financial urgency, willingness to learn,
    and openness to solutions, along with confidence scores and detected keywords.
    
    Args:
        request: MoodAnalysisRequest with user message and conversation depth
        
    Returns:
        MoodAnalysisResponse with detailed mood and emotion analysis
        
    Raises:
        HTTPException: For validation errors
    """
    try:
        logger.info(f"Analyzing mood for message: {request.message[:80]}...")
        
        # Call emotion analyzer
        analysis = analyze_emotion(request.message, request.conversation_depth)
        
        # Check for errors from analyzer
        if "error" in analysis:
            logger.error(f"Emotion analysis error: {analysis['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not analyze mood. Please try again."
            )
        
        # Build response
        response = MoodAnalysisResponse(
            message=request.message,
            stress_level=analysis["stress_level"],
            stress_confidence=analysis["stress_confidence"],
            indicators=analysis["indicators"],
            confidence_scores=analysis["confidence_scores"],
            conversation_phase=analysis["conversation_phase"],
            overall_confidence=analysis["overall_confidence"],
            detected_keywords=analysis.get("detected_keywords")
        )
        
        logger.info(f"Mood analysis complete: stress={response.stress_level}, confidence={response.overall_confidence}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in mood analysis endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error analyzing mood. Please try again."
        )