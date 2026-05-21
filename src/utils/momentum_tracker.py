"""Momentum tracking for wellness improvement trends."""

from __future__ import annotations

from datetime import datetime

from src.utils.wellness_scoring import clamp_score


def calculate_momentum_score(
    *,
    current_overall_score: int,
    previous_overall_score: int | None = None,
    recent_scores: list[int] | None = None,
    recent_timestamps: list[datetime] | None = None,
) -> tuple[int, str]:
    """Return a stable momentum score and a short human-readable label."""

    current = clamp_score(current_overall_score)
    previous = clamp_score(previous_overall_score) if previous_overall_score is not None else current
    recent_scores = [clamp_score(score) for score in (recent_scores or [])]

    improvement = current - previous
    consistency_bonus = 0.0
    if len(recent_scores) >= 2:
        average = sum(recent_scores) / len(recent_scores)
        spread = max(recent_scores) - min(recent_scores)
        consistency_bonus = max(0.0, 12.0 - spread / 5.0) + max(0.0, (current - average) / 6.0)

    recency_bonus = 0.0
    if recent_timestamps and len(recent_timestamps) >= 2:
        most_recent = max(recent_timestamps)
        oldest = min(recent_timestamps)
        days_span = max(1.0, float((most_recent - oldest).days or 1))
        recency_bonus = min(10.0, 30.0 / days_span)

    momentum_score = clamp_score(50 + (improvement * 1.5) + consistency_bonus + recency_bonus)

    if improvement >= 5:
        label = f"+{improvement} this period"
    elif improvement <= -5:
        label = f"{improvement} this period"
    elif momentum_score >= 70:
        label = "Momentum rising"
    elif momentum_score <= 40:
        label = "Momentum needs a reset"
    else:
        label = "Momentum steady"

    return momentum_score, label