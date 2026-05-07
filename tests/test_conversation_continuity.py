from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from src.main import app
from src.routers import chat as chat_router


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


def test_chat_persists_sidebar_metadata_and_resume_payload(monkeypatch):
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

    import uuid

    user_id = str(uuid.uuid4())

    first_response = client.post(
        "/api/v1/chat/",
        json={
            "message": "I need help organizing my loan payments and bills.",
            "user_id": user_id,
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    conversation_id = first_payload["conversation_id"]

    second_response = client.post(
        "/api/v1/chat/",
        json={
            "message": "Can we create a weekly plan for me?",
            "user_id": user_id,
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200

    list_response = client.get(
        "/api/v1/conversations",
        params={"user_id": user_id, "limit": 10, "offset": 0},
    )

    assert list_response.status_code == 200
    conversations = list_response.json()
    assert len(conversations) == 1

    conversation_item = conversations[0]
    assert conversation_item["id"] == conversation_id
    assert conversation_item["title"]
    assert conversation_item["summary"]
    assert conversation_item["last_message_preview"]
    assert conversation_item["last_message_role"] == "assistant"
    assert conversation_item["message_count"] == 4

    resume_response = client.get(
        f"/api/v1/conversations/{conversation_id}/resume",
        params={"user_id": user_id, "limit": 50},
    )

    assert resume_response.status_code == 200
    resume_payload = resume_response.json()
    assert resume_payload["conversation"]["id"] == conversation_id
    assert resume_payload["conversation"]["summary"]
    assert len(resume_payload["messages"]) == 4
    assert resume_payload["messages"][0]["role"] == "user"
    assert resume_payload["messages"][-1]["role"] == "assistant"