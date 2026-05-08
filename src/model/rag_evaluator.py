"""
RAG Answer Evaluator
Uses Gemini as a judge to score responses on relevance, groundedness, and completeness.
Logs scores to model_test_results.json alongside existing mood snapshots.
"""

import json
import logging
import os
import re
import time
import threading
from pathlib import Path

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

EVALUATOR_RESULTS_PATH = Path(__file__).resolve().parent / "model_test_results.json"
_eval_lock = threading.Lock()


def _extract_json_payload(raw_text: str) -> str:
    """Extract a JSON object payload from model output text."""
    text = raw_text.strip()

    # Strip markdown code fences if present.
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()
            if text.startswith("json"):
                text = text[4:].strip()

    # If the model adds prose, keep only the outermost JSON object.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]

    return text


def _extract_float(text: str, key: str) -> float | None:
    match = re.search(rf"\b{re.escape(key)}\b\s*[:=\-]?\s*([01](?:\.\d+)?)", text, re.IGNORECASE)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return max(0.0, min(1.0, value))


def _extract_reason(text: str, key: str) -> str:
    match = re.search(
        rf"\b{re.escape(key)}_reason\b\s*[:=\-]?\s*(.+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return ""
    reason = match.group(1).strip()
    reason = reason.strip('"\' ,')
    return reason[:120]


def _coerce_scores_from_text(raw_text: str) -> dict | None:
    """Best-effort parser when model output is not valid JSON."""
    relevance = _extract_float(raw_text, "relevance")
    groundedness = _extract_float(raw_text, "groundedness")
    completeness = _extract_float(raw_text, "completeness")

    if relevance is None or groundedness is None or completeness is None:
        return None

    return {
        "relevance": relevance,
        "relevance_reason": _extract_reason(raw_text, "relevance"),
        "groundedness": groundedness,
        "groundedness_reason": _extract_reason(raw_text, "groundedness"),
        "completeness": completeness,
        "completeness_reason": _extract_reason(raw_text, "completeness"),
        "failed": False,
        "failure_reason": None,
    }


def _load_results(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Could not load eval results from %s: %s", path, exc)
        return {}


def _save_results(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp.replace(path)


def _build_judge_prompt(
    user_query: str,
    retrieved_chunks: list[str],
    assistant_response: str,
) -> str:
    chunks_text = "\n\n".join(
        f"[Chunk {i+1}]: {chunk[:400]}" for i, chunk in enumerate(retrieved_chunks)
    ) if retrieved_chunks else "No chunks retrieved."

    return f"""You are an expert evaluator for a financial therapy chatbot RAG system.

Score the assistant's response on 3 dimensions. Return ONLY a valid JSON object, no other text.

USER QUERY:
{user_query}

RETRIEVED KNOWLEDGE CHUNKS:
{chunks_text}

ASSISTANT RESPONSE:
{assistant_response}

Score each dimension from 0.0 to 1.0:

1. relevance — Does the response directly address what the user asked?
   - 1.0 = Perfectly on-topic
   - 0.5 = Partially relevant
   - 0.0 = Completely off-topic

2. groundedness — Is the response grounded in the retrieved chunks?
   - 1.0 = Fully supported by retrieved knowledge
   - 0.5 = Partially supported, some assumptions
   - 0.0 = Contradicts or ignores retrieved knowledge

3. completeness — Does the response fully answer the user's need?
   - 1.0 = Complete answer with emotional + practical support
   - 0.5 = Partially complete
   - 0.0 = Missing key information or too vague

Also provide a brief reason (max 15 words) for each score.

Return ONLY this JSON:
{{
  "relevance": 0.0,
  "relevance_reason": "...",
  "groundedness": 0.0,
  "groundedness_reason": "...",
  "completeness": 0.0,
  "completeness_reason": "...",
  "overall_score": 0.0,
  "failed": false,
  "failure_reason": null
}}"""


def evaluate_rag_response(
    *,
    user_query: str,
    retrieved_chunks: list[str],
    assistant_response: str,
    conversation_id: str,
    message_id: str,
    user_id: str,
    file_path: Path | None = None,
) -> dict:
    """
    Score a RAG response using Gemini as judge.
    Logs result to model_test_results.json and returns the score dict.
    Non-blocking on failure — always returns a result dict.
    """
    result = {
        "timestamp": time.time(),
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "user_query": user_query,
        "chunks_retrieved": len(retrieved_chunks),
        "response_length": len(assistant_response),
        "relevance": None,
        "groundedness": None,
        "completeness": None,
        "overall_score": None,
        "failed": False,
        "failure_reason": None,
    }

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            result["failed"] = True
            result["failure_reason"] = "GEMINI_API_KEY not set"
            return result

        client = genai.Client(api_key=api_key)

        prompt = _build_judge_prompt(user_query, retrieved_chunks, assistant_response)

        gemini_response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=512,
                response_mime_type="application/json",
            )
        )

        raw_text = gemini_response.text.strip()
        try:
            scores = json.loads(_extract_json_payload(raw_text))
        except json.JSONDecodeError:
            coerced = _coerce_scores_from_text(raw_text)
            if not coerced:
                raise
            scores = coerced
            logger.warning("RAG evaluator returned malformed JSON; used fallback parser.")

        result["relevance"] = round(float(scores.get("relevance", 0)), 2)
        result["relevance_reason"] = scores.get("relevance_reason", "")
        result["groundedness"] = round(float(scores.get("groundedness", 0)), 2)
        result["groundedness_reason"] = scores.get("groundedness_reason", "")
        result["completeness"] = round(float(scores.get("completeness", 0)), 2)
        result["completeness_reason"] = scores.get("completeness_reason", "")
        result["overall_score"] = round(
            (result["relevance"] + result["groundedness"] + result["completeness"]) / 3, 2
        )
        result["failed"] = bool(scores.get("failed", False))
        result["failure_reason"] = scores.get("failure_reason")

        logger.info(
            "RAG eval: relevance=%.2f groundedness=%.2f completeness=%.2f overall=%.2f [conv=%s]",
            result["relevance"],
            result["groundedness"],
            result["completeness"],
            result["overall_score"],
            conversation_id,
        )

    except json.JSONDecodeError as exc:
        logger.warning("RAG evaluator JSON parse failed: %s", exc)
        result["failed"] = True
        result["failure_reason"] = f"JSON parse error: {exc}"

    except Exception as exc:
        logger.warning("RAG evaluator failed: %s", exc)
        result["failed"] = True
        result["failure_reason"] = str(exc)

    # Always log to file even on failure
    _persist_eval_result(result, file_path or EVALUATOR_RESULTS_PATH)
    return result


def _persist_eval_result(result: dict, path: Path) -> None:
    with _eval_lock:
        data = _load_results(path)
        evals = data.setdefault("rag_evaluations", [])
        evals.append(result)

        # Keep a rolling summary
        successful = [e for e in evals if not e.get("failed") and e.get("overall_score") is not None]
        if successful:
            data["rag_eval_summary"] = {
                "total_evaluated": len(evals),
                "total_failed": len(evals) - len(successful),
                "avg_relevance": round(sum(e["relevance"] for e in successful) / len(successful), 2),
                "avg_groundedness": round(sum(e["groundedness"] for e in successful) / len(successful), 2),
                "avg_completeness": round(sum(e["completeness"] for e in successful) / len(successful), 2),
                "avg_overall": round(sum(e["overall_score"] for e in successful) / len(successful), 2),
                "last_updated": time.time(),
            }

        _save_results(path, data)