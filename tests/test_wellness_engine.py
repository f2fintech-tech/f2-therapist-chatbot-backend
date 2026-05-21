from fastapi.testclient import TestClient

from src.main import app
from src.utils.wellness_scoring import determine_wellness_tier, normalize_test_score


client = TestClient(app)


def test_pressure_scores_invert_to_health_score():
    assert normalize_test_score("debt_pressure_analysis", 80) == 20
    assert normalize_test_score("financial_literacy", 78, normalized_score=78) == 78


def test_wellness_tier_labels_are_safe():
    assert determine_wellness_tier(10) == "Recovering"
    assert determine_wellness_tier(35) == "Stabilizing"
    assert determine_wellness_tier(50) == "Building"
    assert determine_wellness_tier(75) == "Progressing"
    assert determine_wellness_tier(95) == "Thriving"


def test_wellness_endpoint_creates_snapshot():
    payload = {
        "user_id": "11111111-1111-1111-1111-111111111111",
        "test_type": "financial_literacy",
        "raw_score": 4,
        "normalized_score": 80,
        "insights": ["Strong budgeting basics"],
    }

    response = client.post("/api/v1/wellness/test-results", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["wellnessScore"] >= 0
    assert data["wellnessTier"] in {"Recovering", "Stabilizing", "Building", "Progressing", "Thriving"}
    assert "pillars" in data


def test_legacy_dashboard_wellness_route_exists():
    response = client.get("/api/v1/user/11111111-1111-1111-1111-111111111111/wellness-score")
    assert response.status_code == 200
    data = response.json()
    assert {"score", "label", "change_pts", "trend"}.issubset(data)