"""Core Financial Wellness Score calculations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

MAX_SCORE = 100
MIN_SCORE = 0
NEUTRAL_COMPONENT_SCORE = 50

PILLAR_WEIGHTS: dict[str, float] = {
    "money_iq": 0.20,
    "debt_health": 0.20,
    "financial_safety": 0.20,
    "credit_health": 0.15,
    "loan_comfort": 0.10,
    "mood_health": 0.15,
}

TEST_TO_PILLAR: dict[str, str] = {
    "financial_literacy": "money_iq",
    "money_iq": "money_iq",
    "money_iq_arena": "money_iq",
    "debt_balance": "debt_health",
    "debt_pressure": "debt_health",
    "debt_pressure_analysis": "debt_health",
    "stress_metrics": "mood_health",
    "emergency_fund": "financial_safety",
    "financial_safety": "financial_safety",
    "credit_readiness": "credit_health",
    "credit_health": "credit_health",
    "loan_fit": "loan_comfort",
    "loan_comfort": "loan_comfort",
}

PRESSURE_TEST_TYPES = {"debt_balance", "debt_pressure", "debt_pressure_analysis", "stress_metrics"}
WEIGHTED_RECENT_AVERAGES = (0.6, 0.3, 0.1)
WELLNESS_TIERS = (
    (0, 20, "Recovering"),
    (21, 40, "Stabilizing"),
    (41, 60, "Building"),
    (61, 80, "Progressing"),
    (81, 100, "Thriving"),
)


def clamp_score(value: float | int | None, minimum: int = MIN_SCORE, maximum: int = MAX_SCORE) -> int:
    """Clamp a numeric score to the safe 0-100 range and round to the nearest integer."""

    try:
        numeric = float(value) if value is not None else float(NEUTRAL_COMPONENT_SCORE)
    except (TypeError, ValueError):
        numeric = float(NEUTRAL_COMPONENT_SCORE)

    return int(round(max(minimum, min(maximum, numeric))))


def canonical_test_type(test_type: str | None) -> str:
    """Normalize incoming test type labels to a stable internal key."""

    return (test_type or "").strip().lower().replace(" ", "_").replace("-", "_")


def test_type_to_pillar(test_type: str | None) -> str | None:
    """Map a test type to the wellness pillar it influences."""

    return TEST_TO_PILLAR.get(canonical_test_type(test_type))


def scale_to_percent(value: float | int | None) -> int:
    """Scale common test score formats into a 0-100 range."""

    if value is None:
        return NEUTRAL_COMPONENT_SCORE

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return NEUTRAL_COMPONENT_SCORE

    if 0.0 <= numeric <= 1.0:
        return clamp_score(numeric * 100.0)
    if 0.0 <= numeric <= 5.0:
        return clamp_score(numeric * 20.0)
    return clamp_score(numeric)


def normalize_test_score(test_type: str | None, raw_score: float | int | None, normalized_score: float | int | None = None) -> int:
    """Return the stable 0-100 wellness-friendly score for a test result."""

    if normalized_score is not None:
        return clamp_score(normalized_score)

    canonical_type = canonical_test_type(test_type)
    scaled_score = scale_to_percent(raw_score)

    if canonical_type in PRESSURE_TEST_TYPES:
        return clamp_score(MAX_SCORE - scaled_score)

    return scaled_score


def rolling_recent_average(scores: list[float | int]) -> int:
    """Compute a weighted average favoring the most recent entries."""

    if not scores:
        return NEUTRAL_COMPONENT_SCORE

    recent_scores = list(scores)[-3:]
    recent_scores.reverse()

    weighted_total = 0.0
    weight_total = 0.0
    for index, score in enumerate(recent_scores):
        weight = WEIGHTED_RECENT_AVERAGES[index] if index < len(WEIGHTED_RECENT_AVERAGES) else 0.05
        weighted_total += clamp_score(score) * weight
        weight_total += weight

    if weight_total == 0:
        return NEUTRAL_COMPONENT_SCORE

    return clamp_score(weighted_total / weight_total)


def build_pillar_scores(test_results: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate raw test results into one score per wellness pillar."""

    grouped_scores: dict[str, list[tuple[datetime, int]]] = defaultdict(list)

    for result in test_results:
        pillar = test_type_to_pillar(result.get("test_type"))
        if not pillar:
            continue

        completed_at = result.get("completed_at")
        if isinstance(completed_at, str):
            try:
                completed_at = datetime.fromisoformat(completed_at)
            except ValueError:
                completed_at = datetime.utcnow()
        if not isinstance(completed_at, datetime):
            completed_at = datetime.utcnow()

        score = normalize_test_score(
            result.get("test_type"),
            result.get("raw_score"),
            result.get("normalized_score"),
        )
        grouped_scores[pillar].append((completed_at, score))

    breakdown: dict[str, int] = {
        "money_iq": NEUTRAL_COMPONENT_SCORE,
        "debt_health": NEUTRAL_COMPONENT_SCORE,
        "financial_safety": NEUTRAL_COMPONENT_SCORE,
        "credit_health": NEUTRAL_COMPONENT_SCORE,
        "loan_comfort": NEUTRAL_COMPONENT_SCORE,
    }

    for pillar, entries in grouped_scores.items():
        ordered_scores = [score for _, score in sorted(entries, key=lambda item: item[0])]
        breakdown[pillar] = rolling_recent_average(ordered_scores)

    return breakdown


def calculate_mood_health(trend_state: dict[str, Any] | None) -> int:
    """Convert the smoothed mood trend into a stable wellness-friendly score."""

    trend_state = trend_state or {}
    stress = clamp_score(trend_state.get("stress_trend"))
    urgency = clamp_score(trend_state.get("urgency_trend"))
    openness = clamp_score(trend_state.get("openness_trend"))
    willingness = clamp_score(trend_state.get("willingness_trend"))
    emotion = clamp_score(trend_state.get("emotion_trend"))

    mood_health = (
        (MAX_SCORE - stress) * 0.35
        + (MAX_SCORE - urgency) * 0.15
        + openness * 0.20
        + willingness * 0.20
        + emotion * 0.10
    )
    return clamp_score(mood_health)


def calculate_wellness_score(pillars: dict[str, int], mood_health: int) -> int:
    """Combine all wellness pillars into the final rounded 0-100 score."""

    weighted_score = (
        clamp_score(pillars.get("money_iq")) * PILLAR_WEIGHTS["money_iq"]
        + clamp_score(pillars.get("debt_health")) * PILLAR_WEIGHTS["debt_health"]
        + clamp_score(pillars.get("financial_safety")) * PILLAR_WEIGHTS["financial_safety"]
        + clamp_score(pillars.get("credit_health")) * PILLAR_WEIGHTS["credit_health"]
        + clamp_score(pillars.get("loan_comfort")) * PILLAR_WEIGHTS["loan_comfort"]
        + clamp_score(mood_health) * PILLAR_WEIGHTS["mood_health"]
    )
    return clamp_score(weighted_score)


def determine_wellness_tier(score: float | int | None) -> str:
    """Map a score to a psychologically safe wellness label."""

    numeric_score = clamp_score(score)
    for lower, upper, label in WELLNESS_TIERS:
        if lower <= numeric_score <= upper:
            return label
    return "Recovering"


def throttle_score_change(previous_score: float | int | None, proposed_score: float | int, event_type: str = "mood") -> int:
    """Limit abrupt score movement for emotionally-driven updates."""

    previous = clamp_score(previous_score)
    proposed = clamp_score(proposed_score)
    event = canonical_test_type(event_type)

    if previous_score is None:
        return proposed

    max_delta = 2 if event == "mood" else 10 if event in {"test", "test_result", "test_completion"} else 100
    if max_delta >= 100:
        return proposed

    delta = proposed - previous
    delta = max(-max_delta, min(max_delta, delta))
    return clamp_score(previous + delta)


def build_component_snapshot(
    *,
    pillars: dict[str, int],
    mood_health: int,
    overall_score: int,
    momentum_score: int | None = None,
    wellness_tier: str | None = None,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    """Package the computed wellness values in a consistent response shape."""

    return {
        "moneyIQ": clamp_score(pillars.get("money_iq")),
        "debtHealth": clamp_score(pillars.get("debt_health")),
        "financialSafety": clamp_score(pillars.get("financial_safety")),
        "creditHealth": clamp_score(pillars.get("credit_health")),
        "loanComfort": clamp_score(pillars.get("loan_comfort")),
        "moodHealth": clamp_score(mood_health),
        "overallScore": clamp_score(overall_score),
        "momentumScore": clamp_score(momentum_score) if momentum_score is not None else NEUTRAL_COMPONENT_SCORE,
        "wellnessTier": wellness_tier or determine_wellness_tier(overall_score),
        "updatedAt": (updated_at or datetime.utcnow()).isoformat(),
    }