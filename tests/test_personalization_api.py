import os
import shutil
import json
from fastapi.testclient import TestClient
from src.main import app

from src.utils.persona_profiles import DEFAULT_PERSONA_ID

client = TestClient(app)
STORE_DIR = os.path.join(os.getcwd(), "src", "data", "personalization")
PERSONAS_PATH = os.path.join(STORE_DIR, "personas.json")
PREFERENCES_PATH = os.path.join(STORE_DIR, "preferences.json")


def cleanup_store():
    if os.path.isdir(STORE_DIR):
        shutil.rmtree(STORE_DIR)


def test_persona_crud_lifecycle():
    cleanup_store()

    new_persona = {
        "profile_id": "test_coach",
        "name": "Test Coach",
        "description": "A test persona used in CI.",
        "style": {"tone": "encouraging", "empathy_level": 3, "directness": 4, "verbosity": "short", "formality": "neutral", "advice_style": "coaching"},
        "response_goals": ["help quickly"],
        "do_listen": False,
        "do_offer_steps": True,
        "tags": ["test"]
    }

    # Create
    r = client.post("/api/v1/personas", json=new_persona)
    assert r.status_code == 200
    assert r.json()["profile_id"] == "test_coach"

    # List includes new
    r = client.get("/api/v1/personas")
    assert r.status_code == 200
    ids = [p["profile_id"] for p in r.json()]
    assert "test_coach" in ids

    # Get single
    r = client.get("/api/v1/personas/test_coach")
    assert r.status_code == 200
    assert r.json()["name"] == "Test Coach"

    # Update
    updates = {"description": "Updated description from test"}
    r = client.put("/api/v1/personas/test_coach", json=updates)
    assert r.status_code == 200
    assert r.json()["description"] == "Updated description from test"

    # Delete
    r = client.delete("/api/v1/personas/test_coach")
    assert r.status_code == 200

    # Ensure removed in store file
    assert not os.path.exists(PERSONAS_PATH) or "test_coach" not in json.loads(open(PERSONAS_PATH).read())

    cleanup_store()


def test_preferences_crud_lifecycle():
    cleanup_store()

    pref = {
        "user_id": "user123",
        "preferred_tone": "supportive",
        "response_length": "short",
        "detail_level": "high",
        "action_preference": "balanced",
        "question_style": "normal",
        "prefers_emotional_validation": True,
        "prefers_practical_steps": True,
        "prefers_follow_up_questions": False,
        "avoids_topics": ["debt"],
        "notes": "test profile"
    }

    # Create
    r = client.post("/api/v1/preferences", json=pref)
    assert r.status_code == 200
    assert r.json()["user_id"] == "user123"

    # Get
    r = client.get("/api/v1/preferences/user123")
    assert r.status_code == 200
    assert r.json()["response_length"] == "short"

    # Update
    updates = {"response_length": "long", "prefers_follow_up_questions": True}
    r = client.put("/api/v1/preferences/user123", json=updates)
    assert r.status_code == 200
    assert r.json()["response_length"] == "long"
    assert r.json()["prefers_follow_up_questions"] is True

    # Delete
    r = client.delete("/api/v1/preferences/user123")
    assert r.status_code == 200

    # Ensure removed from store
    assert not os.path.exists(PREFERENCES_PATH) or "user123" not in json.loads(open(PREFERENCES_PATH).read())

    cleanup_store()
