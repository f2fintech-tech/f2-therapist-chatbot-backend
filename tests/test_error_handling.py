from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_validation_errors_return_structured_json():
    # Missing the required message field should trigger the request-validation handler.
    response = client.post("/api/v1/chat/analyze-mood", json={"conversation_depth": -1})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "Validation failed"
    assert payload["path"] == "/api/v1/chat/analyze-mood"
    assert isinstance(payload["detail"], list)


def test_http_errors_return_structured_json():
    # Register a tiny throwaway route so we can verify the HTTPException handler shape directly.
    @app.get("/test-http-error")
    def _raise_http_error():
        raise HTTPException(status_code=418, detail="Teapot")

    response = client.get("/test-http-error")

    assert response.status_code == 418
    payload = response.json()
    assert payload["error"] == "Request failed"
    assert payload["detail"] == "Teapot"
    assert payload["path"] == "/test-http-error"
