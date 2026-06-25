import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models import get_db, User, UserConsolidatedProfile

client = TestClient(app)


def test_consolidated_profile_endpoints():
    # 1. Create a dummy user first
    user_id = str(uuid.uuid4())
    db_session: Session = next(get_db())
    
    user = User(
        id=user_id,
        email=f"test_{user_id[:8]}@example.com",
        name="Test User",
        hearts=50,
        is_guest="false"
    )
    db_session.add(user)
    db_session.commit()
    
    try:
        # 2. Test GET consolidated profile (should auto-create with default structure)
        response = client.get(f"/api/v1/profile/consolidated/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert "profile_info" in data
        assert "financial_education" in data
        assert "loan_calculator" in data
        assert data["profile_info"]["name"] == "Test User"
        assert len(data["financial_education"]["videos_seen"]) == 0
        
        # 3. Test track education - video
        video_payload = {
            "content_type": "video",
            "content_id": "vid_101",
            "title": "Introduction to Budgeting"
        }
        resp_edu = client.post(f"/api/v1/profile/track/education/{user_id}", json=video_payload)
        assert resp_edu.status_code == 200
        
        # 4. Test track education - article
        article_payload = {
            "content_type": "article",
            "content_id": "art_202",
            "title": "Understanding Compound Interest"
        }
        resp_art = client.post(f"/api/v1/profile/track/education/{user_id}", json=article_payload)
        assert resp_art.status_code == 200
        
        # 5. Test track loan calculator usage
        calc_payload = {
            "inputs": {
                "principal": 5000,
                "interest_rate": 6.5,
                "term_months": 12
            },
            "results": {
                "monthly_payment": 431.56,
                "total_payment": 5178.72
            }
        }
        resp_calc = client.post(f"/api/v1/profile/track/calculator/{user_id}", json=calc_payload)
        assert resp_calc.status_code == 200
        
        # 6. Test track interaction
        interaction_payload = {
            "event": "clicked_profile_section",
            "details": {
                "section": "goals"
            }
        }
        resp_int = client.post(f"/api/v1/profile/track/interaction/{user_id}", json=interaction_payload)
        assert resp_int.status_code == 200

        # 6.5. Test track platform usage
        usage_payload = {
            "date": "2026-06-25",
            "minutes": 15
        }
        resp_usage = client.post(f"/api/v1/profile/track/usage/{user_id}", json=usage_payload)
        assert resp_usage.status_code == 200
        
        # 7. Query consolidated profile again and verify all values are present in JSON
        response_after = client.get(f"/api/v1/profile/consolidated/{user_id}")
        assert response_after.status_code == 200
        final_data = response_after.json()
        
        # Verify video views
        assert len(final_data["financial_education"]["videos_seen"]) == 1
        assert final_data["financial_education"]["videos_seen"][0]["video_id"] == "vid_101"
        assert final_data["financial_education"]["videos_seen"][0]["title"] == "Introduction to Budgeting"
        assert "watched_at" in final_data["financial_education"]["videos_seen"][0]
        
        # Verify article views
        assert len(final_data["financial_education"]["articles_seen"]) == 1
        assert final_data["financial_education"]["articles_seen"][0]["article_id"] == "art_202"
        assert final_data["financial_education"]["articles_seen"][0]["title"] == "Understanding Compound Interest"
        assert "read_at" in final_data["financial_education"]["articles_seen"][0]
        
        # Verify calculator usage
        assert len(final_data["loan_calculator"]["calculations_performed"]) == 1
        assert final_data["loan_calculator"]["calculations_performed"][0]["inputs"]["principal"] == 5000
        assert final_data["loan_calculator"]["calculations_performed"][0]["results"]["monthly_payment"] == 431.56
        
        # Verify interactions
        assert len(final_data["chatbot_interactions"]) == 1
        assert final_data["chatbot_interactions"][0]["event"] == "clicked_profile_section"
        assert final_data["chatbot_interactions"][0]["details"]["section"] == "goals"

        # Verify platform usage
        assert "platform_usage" in final_data
        assert final_data["platform_usage"]["2026-06-25"] == 15

        
    finally:
        # Clean up database records
        # Delete from consolidated profiles first due to FK constraint
        db_session.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == user_id).delete()
        db_session.query(User).filter(User.id == user_id).delete()
        db_session.commit()
        db_session.close()
