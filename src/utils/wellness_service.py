"""Orchestration helpers for wellness persistence and recalculation."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from src.models import MoodLiveState, MoodTrendState, TestResult, User, WellnessBreakdown
from src.utils.mood_trend_engine import build_live_mood_state, trend_state_to_live_equivalent, update_trend_state
from src.utils.momentum_tracker import calculate_momentum_score
from src.utils.wellness_insights import generate_wellness_insights
from src.utils.wellness_scoring import (
    build_component_snapshot,
    build_pillar_scores,
    calculate_mood_health,
    calculate_wellness_score,
    clamp_score,
    determine_wellness_tier,
    normalize_test_score,
    throttle_score_change,
)


def _serialize_test_result(result: TestResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "user_id": result.user_id,
        "test_type": result.test_type,
        "raw_score": result.raw_score,
        "normalized_score": result.normalized_score,
        "completed_at": result.completed_at,
        "insights": result.insights or [],
        "category_breakdown": result.category_breakdown or {},
    }


def _get_or_create_singleton(session: Session, model, user_id: str):
    instance = session.query(model).filter(model.user_id == user_id).first()
    if instance:
        return instance
    instance = model(user_id=user_id)
    session.add(instance)
    session.flush()
    return instance


def _get_user_score_history(session: Session, user_id: str, limit: int = 5) -> list[int]:
    results = (
        session.query(WellnessBreakdown)
        .filter(WellnessBreakdown.user_id == user_id)
        .order_by(WellnessBreakdown.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [clamp_score(item.overall_score) for item in results if item.overall_score is not None]


def _upsert_user_baseline(session: Session, user_id: str) -> User:
    user = session.query(User).filter(User.id == user_id).first()
    if user:
        return user

    user = User(id=user_id, email=None, name="Guest", hashed_password=None, hearts=50, is_guest="true")
    session.add(user)
    session.flush()
    return user


def record_test_result(
    session: Session,
    *,
    user_id: str,
    test_type: str,
    raw_score: float | int,
    normalized_score: float | int | None = None,
    completed_at: datetime | None = None,
    insights: list[str] | None = None,
    category_breakdown: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one test completion and recalculate the user's wellness state."""

    _upsert_user_baseline(session, user_id)

    result = TestResult(
        id=str(uuid4()),
        user_id=user_id,
        test_type=test_type,
        raw_score=float(raw_score),
        normalized_score=float(normalized_score) if normalized_score is not None else None,
        completed_at=completed_at or datetime.utcnow(),
        insights=insights or [],
        category_breakdown=category_breakdown or {},
    )
    if result.normalized_score is None:
        result.normalized_score = float(normalize_test_score(test_type, raw_score))

    session.add(result)
    session.flush()
    return recalculate_wellness(session, user_id=user_id, event_type="test")


def update_live_mood(
    session: Session,
    *,
    user_id: str,
    mood_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Store the latest live mood state and roll it into the trend state."""

    _upsert_user_baseline(session, user_id)

    live_state = build_live_mood_state(mood_analysis)
    live_row = _get_or_create_singleton(session, MoodLiveState, user_id)
    live_row.stress = live_state["stress"]
    live_row.urgency = live_state["urgency"]
    live_row.openness = live_state["openness"]
    live_row.willingness = live_state["willingness"]
    live_row.emotion = live_state["emotion"]
    live_row.updated_at = datetime.utcnow()

    trend_row = _get_or_create_singleton(session, MoodTrendState, user_id)
    previous_trend = {
        "stress_trend": trend_row.stress_trend,
        "urgency_trend": trend_row.urgency_trend,
        "openness_trend": trend_row.openness_trend,
        "willingness_trend": trend_row.willingness_trend,
        "emotion_trend": trend_row.emotion_trend,
    }
    updated_trend = update_trend_state(previous_trend, live_state)
    trend_row.stress_trend = updated_trend["stress_trend"]
    trend_row.urgency_trend = updated_trend["urgency_trend"]
    trend_row.openness_trend = updated_trend["openness_trend"]
    trend_row.willingness_trend = updated_trend["willingness_trend"]
    trend_row.emotion_trend = updated_trend["emotion_trend"]
    trend_row.updated_at = datetime.utcnow()

    session.flush()
    return recalculate_wellness(session, user_id=user_id, event_type="mood", live_state=live_state)


def recalculate_wellness(
    session: Session,
    *,
    user_id: str,
    event_type: str = "sync",
    live_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute the user's wellness snapshot and persist the latest breakdown."""

    _upsert_user_baseline(session, user_id)

    test_results = (
        session.query(TestResult)
        .filter(TestResult.user_id == user_id)
        .order_by(TestResult.completed_at.asc())
        .all()
    )
    result_payloads = [_serialize_test_result(result) for result in test_results]
    pillars = build_pillar_scores(result_payloads)

    trend_row = session.query(MoodTrendState).filter(MoodTrendState.user_id == user_id).first()
    trend_state = {
        "stress_trend": trend_row.stress_trend if trend_row else 50,
        "urgency_trend": trend_row.urgency_trend if trend_row else 50,
        "openness_trend": trend_row.openness_trend if trend_row else 50,
        "willingness_trend": trend_row.willingness_trend if trend_row else 50,
        "emotion_trend": trend_row.emotion_trend if trend_row else 50,
    }

    mood_health = calculate_mood_health(trend_state)
    proposed_score = calculate_wellness_score(pillars, mood_health)

    current_breakdown = session.query(WellnessBreakdown).filter(WellnessBreakdown.user_id == user_id).first()
    previous_score = current_breakdown.overall_score if current_breakdown else None
    overall_score = throttle_score_change(previous_score, proposed_score, event_type=event_type)
    wellness_tier = determine_wellness_tier(overall_score)

    recent_scores = _get_user_score_history(session, user_id)
    momentum_score, momentum_label = calculate_momentum_score(
        current_overall_score=overall_score,
        previous_overall_score=previous_score,
        recent_scores=recent_scores,
    )

    insights = generate_wellness_insights(
        pillars=pillars,
        mood_health=mood_health,
        live_mood=live_state or trend_state_to_live_equivalent(trend_state),
        trend_state=trend_state,
        momentum_score=momentum_score,
    )

    user = session.query(User).filter(User.id == user_id).first()
    if user:
        user.wellness_score = overall_score
        user.wellness_tier = wellness_tier
        user.momentum_score = momentum_score
        user.updated_at = datetime.utcnow()

    if current_breakdown is None:
        current_breakdown = WellnessBreakdown(user_id=user_id)
        session.add(current_breakdown)

    current_breakdown.money_iq = pillars["money_iq"]
    current_breakdown.debt_health = pillars["debt_health"]
    current_breakdown.financial_safety = pillars["financial_safety"]
    current_breakdown.credit_health = pillars["credit_health"]
    current_breakdown.loan_comfort = pillars["loan_comfort"]
    current_breakdown.mood_health = mood_health
    current_breakdown.overall_score = overall_score
    current_breakdown.wellness_tier = wellness_tier
    current_breakdown.momentum_score = momentum_score
    current_breakdown.insights = insights
    current_breakdown.updated_at = datetime.utcnow()

    session.flush()

    return {
        "userId": user_id,
        "wellnessScore": overall_score,
        "wellnessTier": wellness_tier,
        "momentumScore": momentum_score,
        "momentumLabel": momentum_label,
        "breakdown": build_component_snapshot(
            pillars=pillars,
            mood_health=mood_health,
            overall_score=overall_score,
            momentum_score=momentum_score,
            wellness_tier=wellness_tier,
            updated_at=current_breakdown.updated_at,
        ),
        "pillars": {
            "moneyIQ": pillars["money_iq"],
            "debtHealth": pillars["debt_health"],
            "financialSafety": pillars["financial_safety"],
            "creditHealth": pillars["credit_health"],
            "loanComfort": pillars["loan_comfort"],
            "moodHealth": mood_health,
        },
        "insights": insights,
        "liveMoodState": live_state,
        "trendState": trend_state,
        "updatedAt": current_breakdown.updated_at.isoformat(),
    }


def get_wellness_snapshot(session: Session, user_id: str) -> dict[str, Any]:
    """Read the latest persisted wellness snapshot for a user."""

    breakdown = session.query(WellnessBreakdown).filter(WellnessBreakdown.user_id == user_id).first()
    if not breakdown:
        return recalculate_wellness(session, user_id=user_id, event_type="sync")

    live_state = session.query(MoodLiveState).filter(MoodLiveState.user_id == user_id).first()
    trend_state = session.query(MoodTrendState).filter(MoodTrendState.user_id == user_id).first()
    return {
        "userId": user_id,
        "wellnessScore": clamp_score(breakdown.overall_score),
        "wellnessTier": breakdown.wellness_tier,
        "momentumScore": clamp_score(breakdown.momentum_score),
        "breakdown": build_component_snapshot(
            pillars={
                "money_iq": breakdown.money_iq,
                "debt_health": breakdown.debt_health,
                "financial_safety": breakdown.financial_safety,
                "credit_health": breakdown.credit_health,
                "loan_comfort": breakdown.loan_comfort,
            },
            mood_health=breakdown.mood_health,
            overall_score=breakdown.overall_score,
            momentum_score=breakdown.momentum_score,
            wellness_tier=breakdown.wellness_tier,
            updated_at=breakdown.updated_at,
        ),
        "pillars": {
            "moneyIQ": clamp_score(breakdown.money_iq),
            "debtHealth": clamp_score(breakdown.debt_health),
            "financialSafety": clamp_score(breakdown.financial_safety),
            "creditHealth": clamp_score(breakdown.credit_health),
            "loanComfort": clamp_score(breakdown.loan_comfort),
            "moodHealth": clamp_score(breakdown.mood_health),
        },
        "insights": breakdown.insights or [],
        "liveMoodState": {
            "stress": live_state.stress if live_state else 50,
            "urgency": live_state.urgency if live_state else 50,
            "openness": live_state.openness if live_state else 50,
            "willingness": live_state.willingness if live_state else 50,
            "emotion": live_state.emotion if live_state else 50,
            "updatedAt": live_state.updated_at.isoformat() if live_state else None,
        },
        "trendState": {
            "stress_trend": trend_state.stress_trend if trend_state else 50,
            "urgency_trend": trend_state.urgency_trend if trend_state else 50,
            "openness_trend": trend_state.openness_trend if trend_state else 50,
            "willingness_trend": trend_state.willingness_trend if trend_state else 50,
            "emotion_trend": trend_state.emotion_trend if trend_state else 50,
            "updatedAt": trend_state.updated_at.isoformat() if trend_state else None,
        },
        "updatedAt": breakdown.updated_at.isoformat(),
    }