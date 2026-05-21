"""Rule-based insight generation for the wellness dashboard."""

from __future__ import annotations

from typing import Any

from src.utils.wellness_scoring import clamp_score, determine_wellness_tier


def _has_high(value: Any, threshold: int = 65) -> bool:
    return clamp_score(value) >= threshold


def _has_low(value: Any, threshold: int = 45) -> bool:
    return clamp_score(value) <= threshold


def generate_wellness_insights(
    *,
    pillars: dict[str, Any],
    mood_health: int,
    live_mood: dict[str, Any] | None = None,
    trend_state: dict[str, Any] | None = None,
    momentum_score: int | None = None,
) -> list[str]:
    """Create supportive, non-judgmental insight strings from the score mix."""

    live_mood = live_mood or {}
    trend_state = trend_state or {}
    insights: list[str] = []

    stress_trend = trend_state.get("stress_trend", live_mood.get("stress", 50))
    willingness_trend = trend_state.get("willingness_trend", live_mood.get("willingness", 50))
    openness_trend = trend_state.get("openness_trend", live_mood.get("openness", 50))

    if _has_high(stress_trend) and _has_high(willingness_trend):
        insights.append("You seem financially pressured right now, but highly motivated to improve.")

    if _has_high(pillars.get("money_iq")) and _has_low(pillars.get("financial_safety")):
        insights.append("Your financial understanding is strong, though your safety buffer may need attention.")

    health_average = sum(clamp_score(pillars.get(key)) for key in ("money_iq", "financial_safety", "credit_health", "loan_comfort")) / 4
    if clamp_score(health_average) >= 70 and _has_high(stress_trend):
        insights.append("You appear financially stable overall, though your recent conversations suggest uncertainty around planning decisions.")

    if _has_low(pillars.get("debt_health")) and _has_high(pillars.get("financial_safety")):
        insights.append("Your safety buffer is helping, and lowering debt pressure could strengthen that stability further.")

    if momentum_score is not None and clamp_score(momentum_score) >= 65:
        insights.append("Your recent progress is building useful momentum.")

    if not insights:
        tier = determine_wellness_tier(sum(clamp_score(pillars.get(key)) for key in pillars) / max(1, len(pillars)))
        if tier in {"Recovering", "Stabilizing"}:
            insights.append("There is room to strengthen your setup, and each small step still counts.")
        elif tier in {"Building", "Progressing"}:
            insights.append("You are making steady progress, and targeted improvements can compound well here.")
        else:
            insights.append("Your financial picture looks strong, with room to keep that momentum steady.")

    if _has_high(openness_trend) and _has_low(willingness_trend):
        insights.append("You may be open to ideas, and a simpler next step could make action easier.")

    return insights[:4]