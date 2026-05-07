"""Helpers for lightweight chat A/B experiments and outcome logging."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

CHAT_AB_EXPERIMENT_NAME = "chat_response_style_v1"
CHAT_AB_EXPERIMENT_ENV = "ENABLE_CHAT_AB_TESTING"
EXPERIMENT_LOG_PATH = Path(__file__).resolve().parents[1] / "model" / "experiment_results.json"
_experiment_log_lock = threading.Lock()
POSITIVE_OUTCOME_LABELS = {"positive", "success", "helpful", "resolved", "improved"}


def _is_enabled(env_var: str, default: str = "true") -> bool:
    value = os.getenv(env_var, default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_chat_ab_testing_enabled() -> bool:
    """Return whether the chat experiment layer should be applied."""
    return _is_enabled(CHAT_AB_EXPERIMENT_ENV, default="true")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file_handle:
            payload = json.load(file_handle)
            return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        logger.warning("Failed to load experiment log %s: %s", path, str(exc))
        return {}


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False, indent=2, default=str)
    temp_path.replace(path)


def _append_history(existing_value: Any, new_entry: dict[str, Any]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    if isinstance(existing_value, list):
        history = [entry for entry in existing_value if isinstance(entry, dict)]

    history.append(new_entry)
    return history


def _empty_variant_summary(variant: str) -> dict[str, Any]:
    return {
        "variant": variant,
        "assignment_count": 0,
        "feedback_count": 0,
        "average_rating": None,
        "helpful_rate": None,
        "positive_outcome_rate": None,
        "average_latency_seconds": None,
    }


def _finalize_variant_summary(summary: dict[str, Any]) -> dict[str, Any]:
    feedback_count = summary["feedback_count"]
    assignment_count = summary["assignment_count"]

    if feedback_count > 0:
        summary["average_rating"] = round(summary.pop("_rating_total") / feedback_count, 2)
        summary["helpful_rate"] = round(summary.pop("_helpful_total") / feedback_count, 3)
        summary["positive_outcome_rate"] = round(summary.pop("_positive_total") / feedback_count, 3)
    else:
        summary.pop("_rating_total", None)
        summary.pop("_helpful_total", None)
        summary.pop("_positive_total", None)

    if assignment_count > 0:
        summary["average_latency_seconds"] = round(summary.pop("_latency_total") / assignment_count, 3)
    else:
        summary.pop("_latency_total", None)

    return summary


def load_chat_experiment_summary(
    *,
    experiment_name: str = CHAT_AB_EXPERIMENT_NAME,
    file_path: Path | None = None,
) -> dict[str, Any]:
    """Aggregate assignment and feedback data for the configured chat experiment."""
    target_path = file_path or EXPERIMENT_LOG_PATH
    payload = _load_json(target_path)

    assignments = payload.get("assignment_history", [])
    feedback = payload.get("feedback_history", [])

    variant_summaries: dict[str, dict[str, Any]] = {
        "A": _empty_variant_summary("A"),
        "B": _empty_variant_summary("B"),
    }

    total_assignments = 0
    total_feedback = 0

    for record in assignments:
        if not isinstance(record, dict):
            continue
        if record.get("experiment_name") != experiment_name:
            continue

        variant = str(record.get("variant", "")).upper().strip()
        if variant not in variant_summaries:
            continue

        variant_summaries[variant]["assignment_count"] += 1
        variant_summaries[variant]["_latency_total"] = variant_summaries[variant].get("_latency_total", 0.0) + float(record.get("latency_seconds", 0.0) or 0.0)
        total_assignments += 1

    for record in feedback:
        if not isinstance(record, dict):
            continue
        if record.get("experiment_name") != experiment_name:
            continue

        variant = str(record.get("experiment_variant", "")).upper().strip()
        if variant not in variant_summaries:
            continue

        variant_summary = variant_summaries[variant]
        variant_summary["feedback_count"] += 1
        variant_summary["_rating_total"] = variant_summary.get("_rating_total", 0.0) + float(record.get("rating", 0) or 0)
        variant_summary["_helpful_total"] = variant_summary.get("_helpful_total", 0.0) + (1.0 if record.get("helpful") is True else 0.0)
        outcome = str(record.get("outcome", "")).strip().lower()
        variant_summary["_positive_total"] = variant_summary.get("_positive_total", 0.0) + (1.0 if outcome in POSITIVE_OUTCOME_LABELS else 0.0)
        total_feedback += 1

    finalized_variants = {
        variant: _finalize_variant_summary(summary)
        for variant, summary in variant_summaries.items()
    }

    def _ranking_key(item: tuple[str, dict[str, Any]]) -> tuple[float, float, int]:
        variant, summary = item
        rating = summary.get("average_rating") or 0.0
        helpful_rate = summary.get("helpful_rate") or 0.0
        feedback_count = summary.get("feedback_count") or 0
        return (rating, helpful_rate, feedback_count)

    ranked_variants = sorted(finalized_variants.items(), key=_ranking_key, reverse=True)
    if ranked_variants:
        top_variant, top_summary = ranked_variants[0]
        runner_up = ranked_variants[1][0] if len(ranked_variants) > 1 else None
        if top_summary["feedback_count"] == 0:
            preferred_variant = None
            basis = "No feedback has been recorded yet."
        else:
            preferred_variant = top_variant
            basis = "Ranked by average rating, then helpful rate, then feedback volume."
    else:
        preferred_variant = None
        runner_up = None
        basis = "No variant data found."

    return {
        "experiment_name": experiment_name,
        "total_assignments": total_assignments,
        "total_feedback": total_feedback,
        "variants": finalized_variants,
        "comparison": {
            "preferred_variant": preferred_variant,
            "runner_up_variant": runner_up,
            "basis": basis,
        },
        "generated_at": time.time(),
        "source_path": str(target_path),
    }


def assign_chat_variant(*, user_id: str, conversation_id: str, experiment_name: str = CHAT_AB_EXPERIMENT_NAME) -> dict[str, Any]:
    """Deterministically assign a conversation to a variant."""
    assignment_key = f"{experiment_name}:{user_id}:{conversation_id}"
    digest = hashlib.sha256(assignment_key.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    variant = "A" if bucket < 50 else "B"

    return {
        "experiment_name": experiment_name,
        "assignment_key": assignment_key,
        "bucket": bucket,
        "variant": variant,
    }


def build_chat_variant_guidance(variant: str) -> str:
    """Return the prompt guidance for a given experiment variant."""
    normalized = (variant or "").upper().strip()

    if normalized == "A":
        return (
            "Experiment variant A: stay empathetic and conversational. "
            "Open with validation, then give 1-2 clear next steps, and end with a gentle follow-up question."
        )

    if normalized == "B":
        return (
            "Experiment variant B: lead with the most concrete next action first. "
            "Then give a short explanation and a numbered list of steps while keeping the tone supportive."
        )

    return ""


def log_chat_experiment_assignment(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
    response_text: str,
    latency_seconds: float,
    experiment_assignment: dict[str, Any],
    file_path: Path | None = None,
) -> dict[str, Any]:
    """Append a chat experiment assignment record for later comparison."""
    target_path = file_path or EXPERIMENT_LOG_PATH
    record = {
        "id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "response_length": len(response_text or ""),
        "latency_seconds": round(float(latency_seconds), 3),
        **experiment_assignment,
    }

    with _experiment_log_lock:
        payload = _load_json(target_path)
        payload["assignment_history"] = _append_history(payload.get("assignment_history"), record)
        payload["latest_assignment"] = record
        _save_json(target_path, payload)

    return record


def log_chat_experiment_feedback(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
    experiment_name: str,
    experiment_variant: str,
    rating: int,
    helpful: bool | None = None,
    outcome: str | None = None,
    notes: str | None = None,
    file_path: Path | None = None,
) -> dict[str, Any]:
    """Append user feedback for a variant so outcomes can be compared later."""
    target_path = file_path or EXPERIMENT_LOG_PATH
    record = {
        "id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "experiment_name": experiment_name,
        "experiment_variant": experiment_variant,
        "rating": rating,
        "helpful": helpful,
        "outcome": outcome,
        "notes": notes,
    }

    with _experiment_log_lock:
        payload = _load_json(target_path)
        payload["feedback_history"] = _append_history(payload.get("feedback_history"), record)
        payload["latest_feedback"] = record
        _save_json(target_path, payload)

    return record