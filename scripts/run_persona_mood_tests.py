"""Run the mood analyzer against structured persona scenarios.

By default, results are appended to src/model/model_test_results.json so the
persona runs live alongside the existing model test snapshots.

Usage:
    PYTHONPATH=/workspaces/f2-therapist-chatbot-backend python scripts/run_persona_mood_tests.py
    PYTHONPATH=/workspaces/f2-therapist-chatbot-backend python scripts/run_persona_mood_tests.py --output /tmp/results.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.utils.emotion_analyzer import analyze_emotion


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "persona_mood_cases.json"
DEFAULT_RESULTS = ROOT / "src" / "model" / "model_test_results.json"


def load_fixture(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_fixture(fixture: dict) -> list[dict]:
    results: list[dict] = []
    for persona in fixture.get("personas", []):
        for case in persona.get("test_cases", []):
            analysis = analyze_emotion(case["message"], conversation_depth=0)
            results.append(
                {
                    "persona_id": persona["id"],
                    "persona_name": persona["name"],
                    "label": case["label"],
                    "message": case["message"],
                    "expected_stress_level": case.get("expected_stress_level"),
                    "analysis": analysis,
                }
            )
    return results


def load_existing_results(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def write_results(path: Path, results: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_existing_results(path)

    existing_runs = existing.get("persona_mood_test_runs", [])
    if not isinstance(existing_runs, list):
        existing_runs = []

    run_record = {
        "timestamp": __import__("time").time(),
        "total_cases": len(results),
        "results": results,
    }

    existing_runs.append(run_record)
    existing["persona_mood_test_runs"] = existing_runs
    existing["latest_persona_mood_test_run"] = run_record

    with path.open("w", encoding="utf-8") as handle:
        json.dump(existing, handle, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="Path to persona fixture JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS, help="JSON file to write results")
    args = parser.parse_args()

    fixture = load_fixture(args.fixture)
    results = run_fixture(fixture)

    print(json.dumps(results, indent=2, ensure_ascii=False))

    write_results(args.output, results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())