import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models import get_db, User, TestResult, Base, engine, UserCreditReport, UserConsolidatedProfile

client = TestClient(app)

def test_test_results_saving_and_migration():
    Base.metadata.create_all(bind=engine)
    db: Session = next(get_db())

    guest_id = "test-guest-id-123"
    user_id = "test-real-user-id-456"
    headers = {"Authorization": "Bearer dev_api_key"}

    # Cleanup
    db.query(TestResult).filter(TestResult.user_id.in_([guest_id, user_id])).delete()
    db.query(UserCreditReport).filter(UserCreditReport.user_id.in_([guest_id, user_id])).delete()
    db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id.in_([guest_id, user_id])).delete()
    db.query(User).filter(User.id.in_([guest_id, user_id])).delete()
    db.commit()

    try:
        # Create users
        guest_user = User(id=guest_id, name="Guest User", is_guest="true")
        real_user = User(id=user_id, name="Real User", email="real@finheal.com", is_guest="false")
        db.add(guest_user)
        db.add(real_user)
        db.commit()

        # 1. Save test result for guest
        payload = {
            "user_id": guest_id,
            "test_type": "debt_balance",
            "score": 85,
            "percentage_score": 90,
            "risk_level": "low",
            "category": "debt_free",
            "result_data": {"answers_count": 10}
        }
        resp = client.post("/api/v1/test-results/", json=payload, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["score"] == 85
        assert data["percentage_score"] == 90
        assert data["risk_level"] == "low"
        assert data["category"] == "debt_free"
        assert data["result_data"]["answers_count"] == 10

        # Create guest CIBIL report
        cibil = UserCreditReport(
            id=str(uuid.uuid4()),
            user_id=guest_id,
            bureau="cibil",
            score=750,
            report_data={"accounts": []}
        )
        db.add(cibil)

        # Create guest Consolidated profile
        profile = UserConsolidatedProfile(
            user_id=guest_id,
            data={"financial_education": {"videos_seen": ["vid1"]}}
        )
        db.add(profile)
        db.commit()

        # 2. Query test results for guest
        resp_list = client.get(f"/api/v1/test-results/{guest_id}", headers=headers)
        assert resp_list.status_code == 200
        results = resp_list.json()
        assert len(results) == 1
        assert results[0]["score"] == 85

        # 3. Call migrate endpoint
        migrate_payload = {
            "from_user_id": guest_id,
            "to_user_id": user_id
        }
        migrate_resp = client.post("/api/v1/test-results/migrate", json=migrate_payload, headers=headers)
        assert migrate_resp.status_code == 200
        assert migrate_resp.json() == {"status": "ok"}

        # 4. Verify guest results are now moved to real user
        db.expire_all()
        # Verify TestResult
        user_results = db.query(TestResult).filter(TestResult.user_id == user_id).all()
        assert len(user_results) == 1
        assert user_results[0].category_breakdown["score"] == 85

        # Verify Credit Report
        user_cibil = db.query(UserCreditReport).filter(UserCreditReport.user_id == user_id).first()
        assert user_cibil is not None
        assert user_cibil.score == 750

        # Verify Consolidated Profile
        user_profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == user_id).first()
        assert user_profile is not None
        assert user_profile.data["financial_education"]["videos_seen"] == ["vid1"]

    finally:
        # Cleanup
        db.query(TestResult).filter(TestResult.user_id.in_([guest_id, user_id])).delete()
        db.query(UserCreditReport).filter(UserCreditReport.user_id.in_([guest_id, user_id])).delete()
        db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id.in_([guest_id, user_id])).delete()
        db.query(User).filter(User.id.in_([guest_id, user_id])).delete()
        db.commit()
        db.close()
