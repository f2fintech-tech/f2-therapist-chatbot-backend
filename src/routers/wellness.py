"""Financial wellness score endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models import TestResult, get_db
from src.utils.wellness_scoring import determine_wellness_tier, test_type_to_pillar, PILLAR_WEIGHTS
from src.utils.wellness_service import get_wellness_snapshot, record_test_result, update_live_mood


router = APIRouter(prefix="/wellness", tags=["Wellness"])
legacy_router = APIRouter(tags=["Wellness"])


class TestResultIn(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=36)
    test_type: str = Field(..., min_length=1, max_length=64)
    raw_score: float = Field(..., ge=0, le=100)
    normalized_score: float | None = Field(None, ge=0, le=100)
    completed_at: datetime | None = None
    insights: list[str] | None = None
    category_breakdown: dict[str, Any] | None = None


class MoodEventIn(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=36)
    stress: float = Field(..., ge=0, le=100)
    urgency: float = Field(..., ge=0, le=100)
    openness: float = Field(..., ge=0, le=100)
    willingness: float = Field(..., ge=0, le=100)
    emotion: float = Field(..., ge=0, le=100)


class WellnessResultResponse(BaseModel):
    userId: str
    wellnessScore: int
    wellnessTier: str
    momentumScore: int
    momentumLabel: str | None = None
    breakdown: dict[str, Any]
    pillars: dict[str, Any]
    insights: list[str]
    liveMoodState: dict[str, Any] | None = None
    trendState: dict[str, Any] | None = None
    updatedAt: str


class LegacyWellnessScoreResponse(BaseModel):
    score: int
    label: str
    change_pts: int
    trend: str
    session_count: int | None = None
    goals_count: int | None = None
    active_days: int | None = None


@router.post("/test-results", response_model=WellnessResultResponse, status_code=status.HTTP_201_CREATED)
def submit_test_result(payload: TestResultIn, db: Session = Depends(get_db)):
    """Store one test completion and refresh the wellness score."""

    try:
        response = record_test_result(
            db,
            user_id=payload.user_id,
            test_type=payload.test_type,
            raw_score=payload.raw_score,
            normalized_score=payload.normalized_score,
            completed_at=payload.completed_at,
            insights=payload.insights,
            category_breakdown=payload.category_breakdown,
        )
        db.commit()
        return WellnessResultResponse(**response)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/mood", response_model=WellnessResultResponse, status_code=status.HTTP_200_OK)
def submit_mood_event(payload: MoodEventIn, db: Session = Depends(get_db)):
    """Persist a live mood sample and update the smoothed trend state."""

    try:
        response = update_live_mood(
            db,
            user_id=payload.user_id,
            mood_analysis={
                "stress_confidence": payload.stress / 100.0,
                "confidence_scores": {
                    "financial_urgency": payload.urgency / 100.0,
                    "openness_to_solutions": payload.openness / 100.0,
                    "willingness_to_learn": payload.willingness / 100.0,
                    "emotional_state": payload.emotion / 100.0,
                },
                "indicators": {"emotional_state": None},
            },
        )
        db.commit()
        return WellnessResultResponse(**response)
    except Exception:
        db.rollback()
        raise


@router.get("/{user_id}", response_model=WellnessResultResponse)
def get_user_wellness(user_id: str, db: Session = Depends(get_db)):
    """Read the latest wellness snapshot for a user."""

    try:
        response = get_wellness_snapshot(db, user_id)
        return WellnessResultResponse(**response)
    except Exception:
        db.rollback()
        raise


@legacy_router.get("/user/{user_id}/wellness-score", response_model=LegacyWellnessScoreResponse)
def get_legacy_wellness_score(user_id: str, db: Session = Depends(get_db)):
    """Compatibility endpoint for the generated frontend wellness hook."""

    snapshot = get_wellness_snapshot(db, user_id)
    test_results = (
        db.query(TestResult)
        .filter(TestResult.user_id == user_id)
        .order_by(TestResult.completed_at.desc())
        .all()
    )

    recent_score = int(snapshot.get("wellnessScore", 50))
    momentum_score = int(snapshot.get("momentumScore", 50))

    latest_two_results = test_results[:2]
    # Compute a normalized (weighted) change in overall wellness rather than showing
    # the raw difference between two test scores. This prevents confusing large raw
    # test deltas from being displayed as large overall score swings.
    if len(latest_two_results) >= 2:
        latest_score: Any = latest_two_results[0].normalized_score
        previous_score: Any = latest_two_results[1].normalized_score
        latest_score = float(latest_score)
        previous_score = float(previous_score)
        # Map the latest test to its pillar weight and scale the raw delta by that weight.
        pillar = test_type_to_pillar(latest_two_results[0].test_type)
        weight = PILLAR_WEIGHTS.get(pillar, 0.1)
        change_pts = int(round((latest_score - previous_score) * weight))
    elif len(latest_two_results) == 1:
        latest_score: Any = latest_two_results[0].normalized_score
        latest_score = float(latest_score)
        pillar = test_type_to_pillar(latest_two_results[0].test_type)
        weight = PILLAR_WEIGHTS.get(pillar, 0.1)
        change_pts = int(round((latest_score - 50.0) * weight))
    else:
        change_pts = 0

    if change_pts >= 5:
        trend = "Improving"
    elif change_pts <= -5:
        trend = "Softening"
    else:
        trend = "Steady"

    label = snapshot.get("wellnessTier") or determine_wellness_tier(recent_score)

    active_days = None
    if test_results:
        completed_days = {
            result.completed_at.date().isoformat()
            for result in test_results
            if result.completed_at is not None
        }
        active_days = len(completed_days)

    session_count = len(test_results)

    return LegacyWellnessScoreResponse(
        score=recent_score,
        label=label,
        change_pts=change_pts,
        trend=trend,
        session_count=session_count,
        goals_count=None,
        active_days=active_days,
    )