from fastapi.testclient import TestClient

from src.main import app


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