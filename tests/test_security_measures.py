import logging
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from src.main import app
from src.routers import chat as chat_router


client = TestClient(app)


def test_root_includes_security_headers():
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_oversized_request_is_rejected():
    payload = {
        "message": "x" * 1_200_000,
        "conversation_depth": 0,
    }

    response = client.post("/api/v1/chat/analyze-mood", json=payload)

    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large"


def test_chat_logging_and_snapshot_redact_sensitive_content(monkeypatch, tmp_path, caplog):
    secret_message = "CONFIDENTIAL-REDACTION-CHECK-12345"
    secret_reply = "assistant-reply-CHECK-67890"

    monkeypatch.setattr(chat_router, "analyze_emotion", lambda message, conversation_depth=0: {
        "stress_level": "moderate",
        "stress_confidence": 0.9,
        "indicators": {
            "emotional_state": "anxious",
            "financial_urgency": "urgent",
            "willingness_to_learn": "high",
            "openness_to_solutions": "ready",
        },
        "confidence_scores": {"stress": 0.9},
        "conversation_phase": "discovery",
        "overall_confidence": 0.9,
        "detected_keywords": ["stress"],
    })
    monkeypatch.setattr(
        chat_router,
        "get_llm",
        lambda: RunnableLambda(lambda payload: SimpleNamespace(content=secret_reply)),
    )
    monkeypatch.setattr("src.knowledge.embedder.embed_text", lambda message: [0.1, 0.2, 0.3])

    class _FakeRetriever:
        def get_context(self, query_vector):
            return []

    monkeypatch.setattr("src.knowledge.retriever.KnowledgeRetriever", lambda: _FakeRetriever())
    monkeypatch.setattr(chat_router, "MOOD_SNAPSHOT_RESULTS_PATH", tmp_path / "model_test_results.json")

    import uuid

    user_id = str(uuid.uuid4())

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/v1/chat/",
            json={"message": secret_message, "user_id": user_id},
        )

    assert response.status_code == 200
    assert secret_message not in caplog.text
    assert response.headers.get("X-Client-IP") is None
    assert response.headers.get("X-Process-Time") is not None

    snapshot_file = Path(chat_router.MOOD_SNAPSHOT_RESULTS_PATH)
    stored = snapshot_file.read_text(encoding="utf-8")
    assert secret_message not in stored
    assert secret_reply not in stored
    assert "user_message_fingerprint" in stored
    assert "assistant_response_fingerprint" in stored
