"""Conversation state machine helpers for chat flow control.

This module infers a lightweight conversation stage from recent turns and
builds prompt guidance to avoid repetition, enforce flow, and break loops.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence
import re

TOPIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "loan",
        (
            "loan",
            "emi",
            "repayment",
            "installment",
            "interest rate",
            "tenure",
            "prepay",
            "prepayment",
            "debt consolidation",
        ),
    ),
    (
        "investment",
        (
            "investment",
            "invest",
            "mutual fund",
            "mutual funds",
            "sip",
            "fixed deposit",
            "fd",
            "stock",
            "equity",
            "returns",
        ),
    ),
    (
        "budgeting",
        (
            "budget",
            "budgeting",
            "spend",
            "spending",
            "expense",
            "expenses",
            "cash flow",
        ),
    ),
    (
        "savings",
        (
            "save",
            "savings",
            "emergency fund",
            "rainy day",
        ),
    ),
    (
        "credit",
        (
            "credit score",
            "cibil",
            "credit history",
            "credit card",
        ),
    ),
    (
        "income",
        (
            "salary",
            "income",
            "commission",
            "variable pay",
            "remuneration",
        ),
    ),
    (
        "insurance",
        (
            "insurance",
            "policy",
            "premium",
            "coverage",
        ),
    ),
    (
        "urgency",
        (
            "urgent",
            "emergency",
            "need money quickly",
            "cannot wait",
            "asap",
        ),
    ),
]

DISCOVERY_CUES = (
    "i have",
    "i'm facing",
    "i am facing",
    "my situation",
    "i need help",
    "what should i do",
    "what do i do",
)

EDUCATION_CUES = (
    "what is",
    "how does",
    "difference",
    "compare",
    "explain",
    "why",
    "meaning",
    "how it works",
)

SOLUTION_CUES = (
    "should i",
    "which one",
    "best option",
    "recommend",
    "what next",
    "next step",
    "help me decide",
    "help me choose",
    "plan",
)

FOLLOW_UP_CUES = (
    "already",
    "again",
    "still",
    "you said",
    "you already",
    "not sure",
    "another question",
    "what about",
)


@dataclass(frozen=True)
class ConversationState:
    stage: str
    current_topic: str
    covered_topics: tuple[str, ...]
    repeated_topic: bool
    loop_detected: bool
    loop_reason: str
    evidence: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def _token_set(text: str | None) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", _normalize_text(text)))


def _topic_matches(text: str | None) -> list[str]:
    normalized = _normalize_text(text)
    matches: list[str] = []
    for topic, keywords in TOPIC_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            matches.append(topic)
    return matches


def _extract_covered_topics(prior_texts: Sequence[str] | None) -> list[str]:
    seen: list[str] = []
    for text in prior_texts or []:
        for topic in _topic_matches(text):
            if topic not in seen:
                seen.append(topic)
    return seen


def _has_any_cue(text: str | None, cues: Sequence[str]) -> bool:
    normalized = _normalize_text(text)
    return any(cue in normalized for cue in cues)


def _token_overlap_ratio(left: str | None, right: str | None) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    return len(intersection) / max(len(left_tokens), len(right_tokens))


def infer_conversation_state(current_user_message: str, prior_texts: Sequence[str] | None = None) -> ConversationState:
    """Infer a lightweight conversation stage from recent turns."""

    current_topic_matches = _topic_matches(current_user_message)
    current_topic = current_topic_matches[0] if current_topic_matches else "general"
    covered_topics = _extract_covered_topics(prior_texts)
    repeated_topic = current_topic != "general" and current_topic in covered_topics

    recent_texts = list(prior_texts or [])[-6:]
    similarity_to_last = _token_overlap_ratio(current_user_message, recent_texts[-1] if recent_texts else "")
    same_topic_mentions = sum(1 for text in recent_texts if current_topic != "general" and current_topic in _topic_matches(text))

    loop_reason = ""
    loop_detected = False
    if repeated_topic and same_topic_mentions >= 2:
        loop_detected = True
        loop_reason = f"topic '{current_topic}' has already been covered multiple times"
    elif repeated_topic and similarity_to_last >= 0.5:
        loop_detected = True
        loop_reason = f"current message is very similar to the previous turn on '{current_topic}'"
    elif repeated_topic and _has_any_cue(current_user_message, FOLLOW_UP_CUES):
        loop_detected = True
        loop_reason = f"user is circling back to previously covered topic '{current_topic}'"

    if loop_detected:
        stage = "follow_up"
    elif _has_any_cue(current_user_message, SOLUTION_CUES):
        stage = "solution"
    elif _has_any_cue(current_user_message, EDUCATION_CUES):
        stage = "education"
    elif _has_any_cue(current_user_message, FOLLOW_UP_CUES):
        stage = "follow_up"
    elif _has_any_cue(current_user_message, DISCOVERY_CUES):
        stage = "discovery"
    elif repeated_topic:
        stage = "follow_up"
    elif current_topic != "general":
        stage = "education" if current_topic not in covered_topics else "solution"
    else:
        stage = "discovery"

    evidence = tuple(
        cue
        for cue in (*DISCOVERY_CUES, *EDUCATION_CUES, *SOLUTION_CUES, *FOLLOW_UP_CUES)
        if cue in _normalize_text(current_user_message)
    )

    return ConversationState(
        stage=stage,
        current_topic=current_topic,
        covered_topics=tuple(covered_topics),
        repeated_topic=repeated_topic,
        loop_detected=loop_detected,
        loop_reason=loop_reason,
        evidence=evidence,
    )


def build_conversation_state_guidance(state: ConversationState) -> str:
    """Convert inferred state into prompt instructions."""

    lines = [
        "Conversation state machine:",
        f"- Current stage: {state.stage}",
        f"- Current topic: {state.current_topic}",
        f"- Topics already addressed: {', '.join(state.covered_topics) if state.covered_topics else 'none'}",
    ]

    if state.loop_detected:
        lines.append(f"- Loop detected: {state.loop_reason}.")
        lines.append("- Do not repeat earlier advice. Acknowledge what was already covered and move to a new angle or a short follow-up question.")

    if state.stage == "discovery":
        lines.append("- Discovery: ask 1 or 2 targeted questions to gather missing facts before solving.")
        lines.append("- Avoid jumping straight to recommendations.")
    elif state.stage == "education":
        lines.append("- Education: explain the concept clearly, briefly, and without repeating previous explanations.")
        lines.append("- Use one simple example if it helps.")
    elif state.stage == "solution":
        lines.append("- Solution: provide 2 to 3 practical options with pros and cons, then recommend a next step.")
    elif state.stage == "follow_up":
        lines.append("- Follow-up: summarize what is already covered, then ask one concise question or confirm the next action.")

    lines.append("- Keep the flow progressive: discovery -> education -> solution -> follow-up.")
    return "\n".join(lines)
