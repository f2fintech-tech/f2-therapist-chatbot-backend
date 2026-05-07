from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from src.main import app
from src.routers import chat as chat_router
from src.utils import experiments as experiment_utils


client = TestClient(app)


def _fake_emotion_analysis(message: str, conversation_depth: int = 0):
    return {
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
    }


def _configure_chat_mocks(monkeypatch):
    monkeypatch.setattr(chat_router, "analyze_emotion", _fake_emotion_analysis)
    monkeypatch.setattr(chat_router, "persist_mood_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(
        chat_router,
        "get_llm",
        lambda: RunnableLambda(lambda payload: SimpleNamespace(content="Let's make a simple repayment plan together.")),
    )
    monkeypatch.setattr(
        "src.knowledge.embedder.embed_text",
        lambda message: [0.1, 0.2, 0.3],
    )

    class _FakeRetriever:
        def get_context(self, query_vector):
            return []

    monkeypatch.setattr("src.knowledge.retriever.KnowledgeRetriever", lambda: _FakeRetriever())


def test_chat_returns_experiment_metadata_and_logs_assignment(monkeypatch, tmp_path):
    _configure_chat_mocks(monkeypatch)

    log_path = tmp_path / "experiment_results.json"
    monkeypatch.setattr(experiment_utils, "EXPERIMENT_LOG_PATH", log_path)
    monkeypatch.setenv("ENABLE_CHAT_AB_TESTING", "true")

    import uuid

    user_id = str(uuid.uuid4())
    message = "I need help organizing my loan payments and bills."

    response = client.post(
        "/api/v1/chat/",
        json={"message": message, "user_id": user_id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["experiment"]["enabled"] is True
    assert payload["experiment"]["experiment_name"] == experiment_utils.CHAT_AB_EXPERIMENT_NAME
    assert payload["experiment"]["variant"] in {"A", "B"}

    conversation_id = payload["conversation_id"]
    assignment = experiment_utils.assign_chat_variant(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    assert payload["experiment"]["variant"] == assignment["variant"]

    stored = log_path.read_text(encoding="utf-8")
    assert "assignment_history" in stored
    assert conversation_id in stored


def test_experiment_feedback_endpoint_logs_outcome(monkeypatch, tmp_path):
    _configure_chat_mocks(monkeypatch)

    log_path = tmp_path / "experiment_results.json"
    monkeypatch.setattr(experiment_utils, "EXPERIMENT_LOG_PATH", log_path)
    monkeypatch.setenv("ENABLE_CHAT_AB_TESTING", "true")

    import uuid

    user_id = str(uuid.uuid4())
    message = "Can we create a weekly plan for me?"

    chat_response = client.post(
        "/api/v1/chat/",
        json={"message": message, "user_id": user_id},
    )

    assert chat_response.status_code == 200
    chat_payload = chat_response.json()

    feedback_response = client.post(
        "/api/v1/chat/experiment-feedback",
        json={
            "user_id": user_id,
            "conversation_id": chat_payload["conversation_id"],
            "message_id": chat_payload["message_id"],
            "experiment_name": chat_payload["experiment"]["experiment_name"],
            "experiment_variant": chat_payload["experiment"]["variant"],
            "rating": 5,
            "helpful": True,
            "outcome": "positive",
            "notes": "The response was clear and useful.",
        },
    )

    assert feedback_response.status_code == 201
    feedback_payload = feedback_response.json()
    assert feedback_payload["status"] == "logged"
    assert feedback_payload["experiment_variant"] in {"A", "B"}

    saved = log_path.read_text(encoding="utf-8")
    assert "feedback_history" in saved
    assert "positive" in saved


def test_experiment_summary_endpoint_compares_variants(monkeypatch, tmp_path):
    log_path = tmp_path / "experiment_results.json"
    monkeypatch.setattr(experiment_utils, "EXPERIMENT_LOG_PATH", log_path)

    experiment_name = experiment_utils.CHAT_AB_EXPERIMENT_NAME

    experiment_utils.log_chat_experiment_assignment(
        user_id="11111111-1111-1111-1111-111111111111",
        conversation_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        message_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        response_text="Helpful A response",
        latency_seconds=1.2,
        experiment_assignment={
            "experiment_name": experiment_name,
            "assignment_key": "seed-a-1",
            "bucket": 12,
            "variant": "A",
        },
        file_path=log_path,
    )
    experiment_utils.log_chat_experiment_assignment(
        user_id="22222222-2222-2222-2222-222222222222",
        conversation_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        message_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
        response_text="Helpful A response again",
        latency_seconds=1.0,
        experiment_assignment={
            "experiment_name": experiment_name,
            "assignment_key": "seed-a-2",
            "bucket": 19,
            "variant": "A",
        },
        file_path=log_path,
    )
    experiment_utils.log_chat_experiment_assignment(
        user_id="33333333-3333-3333-3333-333333333333",
        conversation_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        message_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        response_text="Different B response",
        latency_seconds=2.5,
        experiment_assignment={
            "experiment_name": experiment_name,
            "assignment_key": "seed-b-1",
            "bucket": 87,
            "variant": "B",
        },
        file_path=log_path,
    )

    experiment_utils.log_chat_experiment_feedback(
        user_id="11111111-1111-1111-1111-111111111111",
        conversation_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        message_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        experiment_name=experiment_name,
        experiment_variant="A",
        rating=5,
        helpful=True,
        outcome="positive",
        notes="Great response",
        file_path=log_path,
    )
    experiment_utils.log_chat_experiment_feedback(
        user_id="22222222-2222-2222-2222-222222222222",
        conversation_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        message_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
        experiment_name=experiment_name,
        experiment_variant="A",
        rating=4,
        helpful=True,
        outcome="success",
        notes="Still useful",
        file_path=log_path,
    )
    experiment_utils.log_chat_experiment_feedback(
        user_id="33333333-3333-3333-3333-333333333333",
        conversation_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        message_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        experiment_name=experiment_name,
        experiment_variant="B",
        rating=2,
        helpful=False,
        outcome="negative",
        notes="Too vague",
        file_path=log_path,
    )

    response = client.get(
        "/api/v1/chat/experiment-summary",
        params={"experiment_name": experiment_name},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["experiment_name"] == experiment_name
    assert payload["total_assignments"] == 3
    assert payload["total_feedback"] == 3
    assert payload["comparison"]["preferred_variant"] == "A"
    assert payload["comparison"]["runner_up_variant"] == "B"
    assert payload["variants"]["A"]["assignment_count"] == 2
    assert payload["variants"]["A"]["feedback_count"] == 2
    assert payload["variants"]["A"]["average_rating"] == 4.5
    assert payload["variants"]["B"]["feedback_count"] == 1
    assert payload["variants"]["B"]["average_rating"] == 2.0