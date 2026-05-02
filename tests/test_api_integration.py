from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_analyze_mood_endpoint():
    resp = client.post("/api/v1/chat/analyze-mood", json={"message": "I'm very stressed and worried about bills.", "conversation_depth": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "overall_confidence" in data or "stress_level" in data


def test_chat_endpoint_includes_mood():
    # Chat endpoint requires additional fields; include a valid UUID for user_id
    import uuid
    resp = client.post(
        "/api/v1/chat/",
        json={"message": "I need help, I'm anxious about money.", "user_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    # response should include mood info in some form
    assert any(k in data for k in ("mood", "mood_analysis", "mood_snapshot", "latest_mood_snapshot"))
