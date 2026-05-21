"""EMA smoothing for live mood state and mood trend state."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.utils.wellness_scoring import clamp_score

MOOD_ALPHA = 0.1
MOOD_FIELDS = ("stress", "urgency", "openness", "willingness", "emotion")


def _coerce_numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 50.0


def smooth_value(previous_value: Any, current_value: Any, alpha: float = MOOD_ALPHA) -> int:
    """Apply exponential moving average smoothing."""

    previous = _coerce_numeric(previous_value)
    current = _coerce_numeric(current_value)
    return clamp_score((previous * (1.0 - alpha)) + (current * alpha))


def build_live_mood_state(analysis: dict[str, Any], updated_at: datetime | None = None) -> dict[str, Any]:
    """Translate analyzer output into the live mood state shape."""

    indicators = analysis.get("indicators", {}) if isinstance(analysis, dict) else {}
    confidence_scores = analysis.get("confidence_scores", {}) if isinstance(analysis, dict) else {}

    return {
        "stress": clamp_score(round(_coerce_numeric(analysis.get("stress_confidence", 0.0)) * 100.0)),
        "urgency": clamp_score(round(_coerce_numeric(confidence_scores.get("financial_urgency", 0.0)) * 100.0)),
        "openness": clamp_score(round(_coerce_numeric(confidence_scores.get("openness_to_solutions", 0.0)) * 100.0)),
        "willingness": clamp_score(round(_coerce_numeric(confidence_scores.get("willingness_to_learn", 0.0)) * 100.0)),
        "emotion": clamp_score(round(_coerce_numeric(confidence_scores.get("emotional_state", 0.0)) * 100.0)),
        "emotion_label": indicators.get("emotional_state"),
        "updatedAt": (updated_at or datetime.utcnow()).isoformat(),
    }


def update_trend_state(previous_state: dict[str, Any] | None, live_state: dict[str, Any]) -> dict[str, Any]:
    """Smooth the live mood into a slower trend state."""

    previous_state = previous_state or {}
    trend_state: dict[str, Any] = {}

    for field in MOOD_FIELDS:
        live_value = live_state.get(field)
        previous_value = previous_state.get(f"{field}_trend", previous_state.get(field))
        trend_state[f"{field}_trend"] = smooth_value(previous_value, live_value, alpha=MOOD_ALPHA)

    trend_state["updatedAt"] = live_state.get("updatedAt") or datetime.utcnow().isoformat()
    return trend_state


def trend_state_to_live_equivalent(trend_state: dict[str, Any] | None) -> dict[str, Any]:
    """Return a display-friendly copy of the trend state."""

    trend_state = trend_state or {}
    return {field: clamp_score(trend_state.get(f"{field}_trend")) for field in MOOD_FIELDS}