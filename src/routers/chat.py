"""
Chat router with message handling and conversation persistence.
Integrates with Google Gemini 3 flash preview via LangChain and Knowledge Base (RAG).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import os
import logging
import hashlib
import uuid
import re
import time
import json
import threading

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from src.models import (
    get_db, Conversation, ConversationMessage, MessageRole, get_or_create_user
)
from src.utils.validators import (
    sanitize_message, sanitize_string, validate_and_sanitize,
    ValidatedMessage, ValidatedConversation, UUID_PATTERN,
    MAX_MESSAGE_LENGTH, MIN_MESSAGE_LENGTH
)
from src.utils.api_security import require_api_key
from src.utils.emotion_analyzer import analyze_emotion
from src.utils.persona_profiles import get_persona_profile
from src.utils.personalization_context import (
    build_personalization_fallback_guidance,
    resolve_personalization_context,
)
from src.utils.conversation_state import (
    build_conversation_state_guidance,
    infer_conversation_state,
)
from src.utils.experiments import (
    CHAT_AB_EXPERIMENT_NAME,
    assign_chat_variant,
    build_chat_variant_guidance,
    is_chat_ab_testing_enabled,
    load_chat_experiment_summary,
    log_chat_experiment_assignment,
    log_chat_experiment_feedback,
)
from src.utils.user_preferences import get_user_preferences

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"], dependencies=[Depends(require_api_key)])

# ==================== Constants ====================
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
MAX_MESSAGE_LENGTH = 5000
MIN_MESSAGE_LENGTH = 1
CONTEXT_WINDOW_MESSAGES = 10
MOOD_ADAPTATION_ENV = "ENABLE_MOOD_RESPONSE_ADAPTATION"
MOOD_SNAPSHOT_ANALYZER_VERSION = "emotion_analyzer_v1"
MOOD_SNAPSHOT_RESULTS_PATH = Path(__file__).resolve().parents[1] / "model" / "model_test_results.json"
MOOD_SNAPSHOT_TTL_DAYS = 30

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
    title: str | None = Field(None, description="Conversation title")
    mood: dict | None = Field(None, description="User's mood and emotion indicators")
    experiment: dict | None = Field(None, description="Experiment assignment metadata")
    evaluation: dict | None = Field(None, description="Inline RAG evaluation scores when available")
    conversation_state: dict | None = Field(None, description="Conversation flow state and loop detection metadata")


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
    safety_risk: dict | None = None


class ChatExperimentFeedbackRequest(BaseModel):
    """Feedback payload for comparing experiment outcomes."""
    user_id: str = Field(..., min_length=1, max_length=36)
    conversation_id: str = Field(..., min_length=36, max_length=36)
    message_id: str = Field(..., min_length=36, max_length=36)
    experiment_name: str = Field(..., min_length=1, max_length=100)
    experiment_variant: str = Field(..., min_length=1, max_length=20)
    rating: int = Field(..., ge=1, le=5)
    helpful: bool | None = None
    outcome: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=1000)

    @validator('user_id', 'conversation_id', 'message_id')
    def validate_ids(cls, v):
        if not UUID_PATTERN.match(v):
            raise ValueError("Invalid UUID format")
        return v.lower()

    @validator('experiment_variant')
    def validate_variant(cls, v):
        normalized = v.strip().upper()
        if normalized not in {"A", "B"}:
            raise ValueError("Invalid experiment_variant. Must be A or B.")
        return normalized


class ChatExperimentFeedbackResponse(BaseModel):
    """Response model for experiment feedback logging."""
    status: str
    experiment_name: str
    experiment_variant: str
    feedback_id: str
    timestamp: datetime


class ChatExperimentVariantSummary(BaseModel):
    """Aggregated metrics for a single variant."""
    variant: str
    assignment_count: int
    feedback_count: int
    average_rating: float | None = None
    helpful_rate: float | None = None
    positive_outcome_rate: float | None = None
    average_latency_seconds: float | None = None


class ChatExperimentComparisonSummary(BaseModel):
    """Comparison metadata for ranking variants."""
    preferred_variant: str | None = None
    runner_up_variant: str | None = None
    basis: str


class ChatExperimentSummaryResponse(BaseModel):
    """Response model for experiment outcome summaries."""
    experiment_name: str
    total_assignments: int
    total_feedback: int
    variants: dict[str, ChatExperimentVariantSummary]
    comparison: ChatExperimentComparisonSummary
    generated_at: datetime
    source_path: str | None = None

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

@lru_cache(maxsize=1)
def get_finetuned_system_prompt():
    """Load and return the token-optimized finetuned system prompt from file.
    
    This prompt includes explicit response length strategy by conversation stage
    to optimize token usage while maintaining response quality.
    Falls back to generic prompt if file not found.
    """
    finetuned_path = Path(__file__).resolve().parents[2] / "src" / "model" / "finetuned_system_prompt.txt"
    
    try:
        if finetuned_path.exists():
            with open(finetuned_path, 'r', encoding='utf-8') as f:
                prompt = f.read().strip()
                if prompt:
                    logger.info("Loaded finetuned system prompt from %s", finetuned_path)
                    return prompt
        else:
            logger.warning("Finetuned system prompt file not found at %s. Using generic prompt.", finetuned_path)
    except Exception as e:
        logger.warning("Failed to load finetuned system prompt: %s. Using generic prompt.", str(e))
    
    # Fallback to generic prompt
    return get_financial_therapy_prompt()

def get_financial_therapy_prompt():
    """Create and return the financial therapy system prompt.
    
    Returns just the system message string (not a template).
    The user message will be appended directly without template variable substitution.
    """
    system_message = """**# WHO YOU ARE**
You are a compassionate Financial Support Specialist working at F2 Fintech. You are NOT a licensed therapist, counselor, or salesperson.
You are a trusted advisor who genuinely cares about people's financial and emotional wellbeing.

Your core identity:
- Empathetic listener who understands money stress
- Patient educator who explains without jargon
- Honest advisor who prioritizes customer wellbeing over sales
- Non-judgmental supporter who validates feelings
- Practical problem-solver who offers real solutions

**# YOUR PURPOSE**
You listen with therapist-like empathy, offer emotional support, and then help them understand their financial situation and options.
You do not judge them for their past financial decisions or current situation.
You meet them where they are and help them move forward in a way that makes sense for them.
Help people navigate their financial journey with both emotional support and practical guidance, while staying within financial guidance boundaries.
Many customers come to you stressed, confused, or ashamed about their financial situation.
Your job is to make them feel heard, understood, and empowered.

**# BOUNDARIES**
- You can sound warm, human, and deeply attentive.
- You cannot diagnose, treat, or provide mental health therapy.
- You can acknowledge emotions, but you must not present yourself as a therapist.
- If someone expresses self-harm, suicide, or another immediate safety crisis, stop financial advice and direct them to emergency or human support right away.
- If the issue is emotional but not a safety crisis, encourage speaking with a licensed professional or trusted person while continuing with appropriate financial support.

**# HOW YOU COMMUNICATE**

**Tone:**
- Warm, human, and professional (not corporate or robotic)
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

**Professional Boundaries:**
- Do not claim to be a licensed therapist or provide therapy.
- Do not diagnose mental health conditions.
- Do not claim to diagnose mental health conditions.
- Do not overstep into non-financial counseling.
- Keep the tone supportive and steady so the user still feels understood.

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

**List of Financial Concepts You Can Explain but not limited to:**
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
- If they mention self-harm or suicide, stop financial guidance and direct them to immediate emergency or human support.

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

**# RESPONSE FORMAT**
Return valid JSON only with this structure:
{
    "response": "Your final user-facing reply here",
    "evaluation": {
        "relevance": 0.0,
        "groundedness": 0.0,
        "completeness": 0.0
    }
}

Remember: This is a conversation with a real person facing real stress. Treat them with
the dignity, respect, and patience you'd want if you were in their shoes."""

    return system_message


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


def _parse_structured_chat_output(text: str) -> tuple[str, dict | None]:
    """Parse the chat model's JSON output into response text and evaluation scores."""
    try:
        data = json.loads(text)
        response_text = str(data.get("response", ""))
        evaluation = data.get("evaluation", {})
        if not isinstance(evaluation, dict):
            evaluation = {}
        parsed_evaluation = {
            "relevance": float(evaluation.get("relevance", 0.5)),
            "groundedness": float(evaluation.get("groundedness", 0.5)),
            "completeness": float(evaluation.get("completeness", 0.5)),
            "parsed": True,
        }
        return response_text, parsed_evaluation
    except Exception:
        return text, None


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


def _build_safety_response(mood_analysis: dict | None) -> str:
    """Build a safe fallback response when immediate safety risk is detected."""
    safety_risk = (mood_analysis or {}).get("safety_risk", {})
    if safety_risk.get("level") != "immediate":
        return ""

    return (
        "I’m really sorry you’re carrying this much right now. I can’t help with immediate self-harm or suicide situations here. "
        "Please contact emergency services or a trusted person right now, and move to a safer place if you can. "
        "If this is not an immediate safety issue and you want to talk about the financial side, I can help with that next."
    )


def _build_experiment_guidance(variant: str | None) -> str:
    if not variant:
        return ""
    guidance = build_chat_variant_guidance(variant)
    if not guidance:
        return ""
    return f"A/B testing guidance:\n{guidance}"


def _build_persona_guidance(persona_profile) -> str:
    """Convert a persona profile into a compact instruction block for the model.

    Step 3 keeps the integration simple: the route loads a persona profile and
    turns it into a prompt-ready summary, but it does not yet add UI controls or
    a persistence layer for choosing the persona.
    """

    if not persona_profile:
        return ""

    style = persona_profile.style
    lines = [
        "Persona guidance:",
        f"- Persona name: {persona_profile.name}",
        f"- Description: {persona_profile.description}",
        f"- Tone: {style.tone}",
        f"- Empathy level: {style.empathy_level}/5",
        f"- Directness: {style.directness}/5",
        f"- Verbosity: {style.verbosity}",
        f"- Formality: {style.formality}",
        f"- Advice style: {style.advice_style}",
    ]

    if persona_profile.do_listen:
        lines.append("- Start by listening and validating the user's concern.")
    if persona_profile.do_offer_steps:
        lines.append("- Include clear next steps after the emotional acknowledgment.")
    if persona_profile.response_goals:
        lines.append("- Response goals:")
        lines.extend(f"  - {goal}" for goal in persona_profile.response_goals)
    if persona_profile.tags:
        lines.append(f"- Tags: {', '.join(persona_profile.tags)}")

    return "\n".join(lines)


def _build_user_preference_guidance(user_preferences) -> str:
    """Convert stored user preferences into prompt instructions.

    The preferences are loaded for each request so future persistence work can
    immediately shape the response without changing the chat route again.
    """

    if not user_preferences:
        return ""

    lines = [
        "User preference guidance:",
        f"- Preferred tone: {user_preferences.preferred_tone or 'default'}",
        f"- Response length: {user_preferences.response_length}",
        f"- Detail level: {user_preferences.detail_level}",
        f"- Action preference: {user_preferences.action_preference}",
        f"- Question style: {user_preferences.question_style}",
    ]

    if user_preferences.prefers_emotional_validation:
        lines.append("- Prioritize emotional validation before advice.")
    if user_preferences.prefers_practical_steps:
        lines.append("- Offer practical steps the user can try right away.")
    if user_preferences.prefers_follow_up_questions:
        lines.append("- Ask a short follow-up question if clarification would help.")
    if user_preferences.avoids_topics:
        lines.append(f"- Avoid topics: {', '.join(user_preferences.avoids_topics)}")
    if user_preferences.notes:
        lines.append(f"- Notes: {user_preferences.notes}")

    return "\n".join(lines)


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


def _snapshot_retention_seconds() -> int:
    """Return how long mood snapshots should be retained before pruning."""
    raw_days = os.getenv("MOOD_SNAPSHOT_TTL_DAYS")
    try:
        days = int(raw_days) if raw_days is not None else MOOD_SNAPSHOT_TTL_DAYS
    except (TypeError, ValueError):
        days = MOOD_SNAPSHOT_TTL_DAYS
    return max(1, days) * 24 * 60 * 60


def _snapshot_timestamp(item: dict) -> float | None:
    """Extract a comparable timestamp from a persisted snapshot."""
    timestamp = item.get("timestamp")
    if isinstance(timestamp, (int, float)):
        return float(timestamp)
    return None


def _prune_expired_snapshots(snapshots: list[dict]) -> None:
    """Drop mood snapshots that are older than the configured retention window."""
    cutoff = time.time() - _snapshot_retention_seconds()
    snapshots[:] = [
        snapshot
        for snapshot in snapshots
        if (snapshot_time := _snapshot_timestamp(snapshot)) is None or snapshot_time >= cutoff
    ]


def _message_fingerprint(message: str | None) -> dict[str, int | str]:
    """Return non-reversible message metadata for analytics."""
    normalized_message = (message or "").strip()
    digest = hashlib.sha256(normalized_message.encode("utf-8")).hexdigest()
    return {
        "hash": digest,
        "length": len(normalized_message),
    }


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
    file_path: Path | None = None,
) -> None:
    """Persist a mood snapshot to JSON for analytics/auditing without DB tables."""
    stress_level = mood_analysis.get("stress_level")

    with _mood_snapshot_lock:
        file_path = file_path or MOOD_SNAPSHOT_RESULTS_PATH
        data = _load_results_file(file_path)
        snapshots = data.setdefault("mood_snapshots", [])
        _prune_expired_snapshots(snapshots)

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
            "user_message_fingerprint": _message_fingerprint(user_message),
            "assistant_response_fingerprint": _message_fingerprint(assistant_response),
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

def save_message(db: Session, conversation_id: str, role: MessageRole, content: str, mood: dict | None = None):
    """Save a message to the database with optional mood data."""
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
        content=validated_content,
        mood=mood
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def _truncate_preview(text: str, limit: int = 120) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _generate_conversation_title(user_message: str) -> str:
    """Create a short, readable title from the first user message."""
    preview = _truncate_preview(user_message, limit=64)
    return preview or "New conversation"


def _generate_conversation_summary(user_message: str, assistant_message: str) -> str:
    """Create a compact summary for sidebar previews."""
    user_preview = _truncate_preview(user_message, limit=72)
    assistant_preview = _truncate_preview(assistant_message, limit=72)
    return f"You: {user_preview} | Assistant: {assistant_preview}"


def _build_mood_dimensions(mood_analysis: dict) -> dict[str, float]:
    """Translate analyzer output into 0-100 dimensions for the insights panel."""
    confidence_scores = mood_analysis.get("confidence_scores", {})
    stress_confidence = mood_analysis.get("stress_confidence", 0.0)

    return {
        "stress": round(float(stress_confidence) * 100, 2),
        "urgency": round(float(confidence_scores.get("financial_urgency", 0.0)) * 100, 2),
        "openness": round(float(confidence_scores.get("openness_to_solutions", 0.0)) * 100, 2),
        "willingness": round(float(confidence_scores.get("willingness_to_learn", 0.0)) * 100, 2),
        "emotion": round(float(confidence_scores.get("emotional_state", 0.0)) * 100, 2),
    }

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

        safety_response = _build_safety_response(mood_analysis)
        if safety_response:
            logger.warning("Immediate safety risk detected for user %s in conversation %s", request.user_id, conversation.id)

            # Build mood data to store with message
            mood_to_store = {
                "stress_level": mood_analysis.get("stress_level"),
                "emotional_state": mood_analysis.get("indicators", {}).get("emotional_state"),
                "financial_urgency": mood_analysis.get("indicators", {}).get("financial_urgency"),
                "willingness_to_learn": mood_analysis.get("indicators", {}).get("willingness_to_learn"),
                "openness_to_solutions": mood_analysis.get("indicators", {}).get("openness_to_solutions"),
                "stress_confidence": mood_analysis.get("stress_confidence"),
                "overall_confidence": mood_analysis.get("overall_confidence"),
                "dimensions": _build_mood_dimensions(mood_analysis),
                "safety_risk": mood_analysis.get("safety_risk"),
            }

            assistant_message_obj = save_message(
                db, conversation.id, MessageRole.ASSISTANT, safety_response, mood=mood_to_store
            )

            conversation_title = conversation.title or _generate_conversation_title(request.message)
            if not conversation.title:
                conversation.title = conversation_title

            conversation.summary = _generate_conversation_summary(request.message, safety_response)

            persist_mood_snapshot(
                user_id=request.user_id,
                conversation_id=conversation.id,
                user_message_id=user_message_obj.id,
                assistant_message_id=assistant_message_obj.id,
                user_message=request.message,
                assistant_response=safety_response,
                mood_analysis=mood_analysis,
                conversation_depth=conversation_depth,
                model_name="gemini-3-flash-preview",
            )

            conversation.message_count += 2
            conversation.updated_at = datetime.utcnow()
            db.commit()

            return ChatResponse(
                response=safety_response,
                user_id=request.user_id,
                conversation_id=conversation.id,
                message_id=assistant_message_obj.id,
                timestamp=datetime.utcnow(),
                title=conversation_title,
                mood={
                    "stress_level": mood_analysis.get("stress_level"),
                    "emotional_state": mood_analysis.get("indicators", {}).get("emotional_state"),
                    "financial_urgency": mood_analysis.get("indicators", {}).get("financial_urgency"),
                    "willingness_to_learn": mood_analysis.get("indicators", {}).get("willingness_to_learn"),
                    "openness_to_solutions": mood_analysis.get("indicators", {}).get("openness_to_solutions"),
                    "stress_confidence": mood_analysis.get("stress_confidence"),
                    "overall_confidence": mood_analysis.get("overall_confidence"),
                    "dimensions": _build_mood_dimensions(mood_analysis),
                    "safety_risk": mood_analysis.get("safety_risk"),
                },
            )

        experiment_enabled = is_chat_ab_testing_enabled()
        experiment_assignment = None
        experiment_guidance_text = ""
        if experiment_enabled:
            experiment_assignment = assign_chat_variant(
                user_id=request.user_id,
                conversation_id=conversation.id,
                experiment_name=CHAT_AB_EXPERIMENT_NAME,
            )
            experiment_guidance_text = _build_experiment_guidance(experiment_assignment.get("variant"))
            logger.info(
                "Experiment assignment applied: %s variant %s (bucket %s)",
                experiment_assignment.get("experiment_name"),
                experiment_assignment.get("variant"),
                experiment_assignment.get("bucket"),
            )

        # Resolve the user's personalization context once so we can reuse the
        # same fallback-aware defaults throughout the rest of the route.
        personalization_context = resolve_personalization_context(request.user_id)
        persona_profile = personalization_context.persona_profile
        user_preferences = personalization_context.user_preferences
        persona_guidance_text = _build_persona_guidance(persona_profile)
        preference_guidance_text = _build_user_preference_guidance(user_preferences)
        fallback_guidance_text = build_personalization_fallback_guidance(personalization_context)
        if persona_guidance_text:
            logger.info("Persona guidance applied to prompt: %s", persona_profile.name)
        if preference_guidance_text:
            logger.info("User preference guidance applied to prompt for %s", request.user_id)
        if fallback_guidance_text:
            logger.info(
                "Personalization fallback applied for %s (default persona=%s, default preferences=%s)",
                request.user_id,
                personalization_context.used_default_persona,
                personalization_context.used_default_preferences,
            )

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
        prior_turn_texts = [
            f"{'User' if msg.role == MessageRole.USER else 'Assistant'}: {msg.content}"
            for msg in prior_context_messages
            if getattr(msg, "content", None)
        ]
        conversation_state = infer_conversation_state(request.message, prior_turn_texts)
        conversation_state_guidance = build_conversation_state_guidance(conversation_state)
        logger.info(
            "Conversation state inferred for %s: stage=%s, topic=%s, loop=%s",
            conversation.id,
            conversation_state.stage,
            conversation_state.current_topic,
            conversation_state.loop_detected,
        )

        # ==================== NEW: RAG Integration ====================
        # Retrieve relevant knowledge from Pinecone
        logger.info("Retrieving knowledge base context for user message")

        context_text = ""
        knowledge_context = []

        try:
            from src.knowledge.retriever import get_relevant_context

            knowledge_context = get_relevant_context(request.message)
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

        if persona_guidance_text:
            enhanced_message_parts.append(persona_guidance_text)

        if preference_guidance_text:
            enhanced_message_parts.append(preference_guidance_text)

        if fallback_guidance_text:
            enhanced_message_parts.append(fallback_guidance_text)

        if mood_guidance_text:
            enhanced_message_parts.append(mood_guidance_text)

        if experiment_guidance_text:
            enhanced_message_parts.append(experiment_guidance_text)

        if conversation_state_guidance:
            enhanced_message_parts.append(conversation_state_guidance)

        enhanced_message_parts.append(f"**User's Question:**\n{request.message}")
        enhanced_message = "\n".join(enhanced_message_parts)

        logger.info(f"Enhanced message length: {len(enhanced_message)} characters")

        # Initialize LLM
        llm = get_llm()
        system_prompt = get_finetuned_system_prompt()

        # Create messages directly (avoiding template variable substitution issues with braces in user message)
        generation_start = time.perf_counter()
        max_retries = 2
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=enhanced_message)
                ]
                response = llm.invoke(messages)
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

        # Parse structured output so we can save the assistant response and inline evaluation scores.
        assistant_text = None
        evaluation = None
        try:
            # Handle AIMessage objects from LangChain - content can be list (multimodal) or string
            if hasattr(response, 'content'):
                content = response.content
                
                # If content is a list (multimodal response), extract text from each item
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and 'text' in item:
                            text_parts.append(item['text'])
                        elif isinstance(item, str):
                            text_parts.append(item)
                    raw_text = ''.join(text_parts)
                else:
                    raw_text = str(content) if not isinstance(content, str) else content
            else:
                raw_text = str(response)
            
            logger.info(f"raw_text (first 200): {raw_text[:200]}")
            assistant_text, evaluation = _parse_structured_chat_output(raw_text)
            logger.info(f"Successfully parsed assistant_text (first 200): {assistant_text[:200] if assistant_text else 'None'}")
        except Exception as e:
            logger.warning(f"Failed to parse structured output: {e}", exc_info=True)
            # Fallback: try to get content as string
            if hasattr(response, 'content'):
                content = response.content
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and 'text' in item:
                            text_parts.append(item['text'])
                        elif isinstance(item, str):
                            text_parts.append(item)
                    assistant_text = ''.join(text_parts)
                else:
                    assistant_text = str(content) if not isinstance(content, str) else content
            else:
                assistant_text = str(response)
            evaluation = None

        # Build mood data to store with message
        mood_to_store = {
            "stress_level": mood_analysis.get("stress_level"),
            "emotional_state": mood_analysis.get("indicators", {}).get("emotional_state"),
            "financial_urgency": mood_analysis.get("indicators", {}).get("financial_urgency"),
            "willingness_to_learn": mood_analysis.get("indicators", {}).get("willingness_to_learn"),
            "openness_to_solutions": mood_analysis.get("indicators", {}).get("openness_to_solutions"),
            "stress_confidence": mood_analysis.get("stress_confidence"),
            "overall_confidence": mood_analysis.get("overall_confidence"),
            "dimensions": _build_mood_dimensions(mood_analysis),
        }

        # Save assistant message with mood data
        assistant_message_obj = save_message(
            db, conversation.id, MessageRole.ASSISTANT, assistant_text, mood=mood_to_store
        )
        logger.info(f"Assistant message saved: {assistant_message_obj.id}")

        if not conversation.title:
            conversation.title = _generate_conversation_title(request.message)
        conversation_title = conversation.title

        conversation.summary = _generate_conversation_summary(request.message, assistant_text)

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

        if experiment_enabled and experiment_assignment:
            try:
                log_chat_experiment_assignment(
                    user_id=request.user_id,
                    conversation_id=conversation.id,
                    message_id=assistant_message_obj.id,
                    response_text=assistant_text,
                    latency_seconds=time.perf_counter() - request_start,
                    experiment_assignment=experiment_assignment,
                )
            except Exception as exc:
                logger.warning("Experiment assignment logging failed: %s", str(exc), exc_info=True)

        logger.info(f"Chat exchange completed for user {request.user_id} in conversation {conversation.id}")
        logger.info(f"Response length: {len(assistant_text)} characters")
        logger.info("Total chat request completed in %.2fs", time.perf_counter() - request_start)

        experiment_response = None
        if experiment_enabled and experiment_assignment:
            experiment_response = {
                "enabled": True,
                "experiment_name": experiment_assignment.get("experiment_name"),
                "variant": experiment_assignment.get("variant"),
                "bucket": experiment_assignment.get("bucket"),
                "assignment_key": experiment_assignment.get("assignment_key"),
            }

        return ChatResponse(
            response=assistant_text,
            user_id=request.user_id,
            conversation_id=conversation.id,
            message_id=assistant_message_obj.id,
            timestamp=datetime.utcnow(),
            title=conversation_title,
            experiment=experiment_response,
            mood={
                "stress_level": mood_analysis.get("stress_level"),
                "emotional_state": mood_analysis.get("indicators", {}).get("emotional_state"),
                "financial_urgency": mood_analysis.get("indicators", {}).get("financial_urgency"),
                "willingness_to_learn": mood_analysis.get("indicators", {}).get("willingness_to_learn"),
                "openness_to_solutions": mood_analysis.get("indicators", {}).get("openness_to_solutions"),
                "stress_confidence": mood_analysis.get("stress_confidence"),
                "overall_confidence": mood_analysis.get("overall_confidence"),
                "dimensions": _build_mood_dimensions(mood_analysis),
            }
            ,
            evaluation=evaluation,
            conversation_state=conversation_state.to_dict(),
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


@router.post("/experiment-feedback", response_model=ChatExperimentFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_chat_experiment_feedback(
    request: ChatExperimentFeedbackRequest,
):
    """Log user feedback for an experiment variant so outcomes can be compared later."""
    try:
        feedback = log_chat_experiment_feedback(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            message_id=request.message_id,
            experiment_name=request.experiment_name,
            experiment_variant=request.experiment_variant,
            rating=request.rating,
            helpful=request.helpful,
            outcome=request.outcome,
            notes=request.notes,
        )

        return ChatExperimentFeedbackResponse(
            status="logged",
            experiment_name=feedback["experiment_name"],
            experiment_variant=feedback["experiment_variant"],
            feedback_id=feedback["id"],
            timestamp=datetime.utcnow(),
        )

    except ValueError as e:
        logger.warning("Invalid experiment feedback payload: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid experiment feedback data",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error logging experiment feedback: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error logging experiment feedback",
        )


@router.get("/experiment-summary", response_model=ChatExperimentSummaryResponse)
async def get_chat_experiment_summary(
    experiment_name: str = Query(CHAT_AB_EXPERIMENT_NAME, min_length=1, max_length=100),
):
    """Summarize A/B experiment performance across assignments and user feedback."""
    try:
        summary = load_chat_experiment_summary(experiment_name=experiment_name)

        return ChatExperimentSummaryResponse(
            experiment_name=summary["experiment_name"],
            total_assignments=summary["total_assignments"],
            total_feedback=summary["total_feedback"],
            variants={
                variant: ChatExperimentVariantSummary(**variant_summary)
                for variant, variant_summary in summary["variants"].items()
            },
            comparison=ChatExperimentComparisonSummary(**summary["comparison"]),
            generated_at=datetime.utcfromtimestamp(summary["generated_at"]),
            source_path=summary.get("source_path"),
        )

    except Exception as e:
        logger.error("Error building experiment summary: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error building experiment summary",
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
        logger.info("Analyzing mood for incoming user message")

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
            detected_keywords=analysis.get("detected_keywords"),
            safety_risk=analysis.get("safety_risk")
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


# ==================== Generate Conversation Title Endpoint ====================
