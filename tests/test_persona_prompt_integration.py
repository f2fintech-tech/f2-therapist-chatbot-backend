"""Integration test for loading persona profiles and user preferences into the chat prompt."""

from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from src.main import app
from src.routers import chat as chat_router


client = TestClient(app)


def _extract_prompt_text(payload):
    """Convert LangChain prompt payloads into a readable string for assertions."""

    if hasattr(payload, "to_messages"):
        return "\n".join(getattr(message, "content", str(message)) for message in payload.to_messages())
    if isinstance(payload, dict):
        return "\n".join(f"{key}: {value}" for key, value in payload.items())
    return str(payload)


def _configure_chat_mocks(monkeypatch, prompt_capture):
    """Stub the external dependencies so we can inspect the prompt text cleanly."""

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
    monkeypatch.setattr(chat_router, "persist_mood_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(
        chat_router,
        "get_llm",
        lambda: RunnableLambda(
            lambda payload: prompt_capture.setdefault("prompt_text", _extract_prompt_text(payload)) or SimpleNamespace(
                content="Let's make a simple repayment plan together."
            )
        ),
    )
    monkeypatch.setattr(
        "src.knowledge.embedder.embed_text",
        lambda message: [0.1, 0.2, 0.3],
    )

    class _FakeRetriever:
        def get_context(self, query_vector):
            return []

    monkeypatch.setattr("src.knowledge.retriever.KnowledgeRetriever", lambda: _FakeRetriever())


def test_chat_prompt_includes_persona_and_user_preferences(monkeypatch):
    """The chat route should load step-1 and step-2 settings into the prompt."""

    prompt_capture = {}
    _configure_chat_mocks(monkeypatch, prompt_capture)

    import uuid

    user_id = str(uuid.uuid4())

    response = client.post(
        "/api/v1/chat/",
        json={"message": "I need help organizing my loan payments and bills.", "user_id": user_id},
    )

    assert response.status_code == 200
    prompt_text = prompt_capture["prompt_text"]

    assert "Persona guidance:" in prompt_text
    assert "Balanced Support" in prompt_text
    assert "User preference guidance:" in prompt_text
    assert "Preferred tone: supportive" in prompt_text
    assert "Response length: medium" in prompt_text
