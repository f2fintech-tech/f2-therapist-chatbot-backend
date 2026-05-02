"""Append-only storage helpers for model_test_results.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_RESULTS_PATH = Path("src/model/model_test_results.json")
MAX_HISTORY = 0  # 0 means keep all history entries


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _append_history(existing_value: Any, new_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    if isinstance(existing_value, list):
        history = [entry for entry in existing_value if isinstance(entry, dict)]

    history.append(new_entry)
    if MAX_HISTORY > 0:
        return history[-MAX_HISTORY:]
    return history


def append_test_result(results_summary: Dict[str, Any], output_path: Path = DEFAULT_RESULTS_PATH) -> Path:
    """Append a result run to the shared JSON file without removing previous runs."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_json(output_path)
    mode = str(results_summary.get("mode", "")).lower()
    new_entry = {**results_summary}

    if "persona" in mode:
        existing["persona_mood_test_runs"] = _append_history(existing.get("persona_mood_test_runs"), new_entry)
        existing["latest_persona_mood_test_run"] = new_entry
    elif "pain_point" in mode:
        existing["pain_point_scenario_test_runs"] = _append_history(existing.get("pain_point_scenario_test_runs"), new_entry)
        existing["latest_pain_point_test_run"] = new_entry
    else:
        existing["run_history"] = _append_history(existing.get("run_history"), new_entry)
        existing["latest_run"] = new_entry
        existing["timestamp"] = results_summary.get("timestamp", existing.get("timestamp"))
        existing["mode"] = results_summary.get("mode", existing.get("mode"))
        existing["model"] = results_summary.get("model", existing.get("model"))
        existing["prompt_type"] = results_summary.get("prompt_type", existing.get("prompt_type"))

    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(existing, file_handle, indent=2, default=str)

    return output_path
