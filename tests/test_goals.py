import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models import get_db, User, Base, engine

client = TestClient(app)

def test_goals_crud_endpoint():
    # Create all tables for the SQLite in-memory test database
    Base.metadata.create_all(bind=engine)

    # 1. Create a dummy user
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
        # 2. Test GET profile first (should have empty goals list)
        response = client.get(f"/api/v1/auth/profile/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert "goals" in data
        assert data["goals"] == []
        
        # 3. Test update goals (PUT)
        goals_payload = [
            {
                "id": "goal-1",
                "userId": user_id,
                "name": "Save for a Car",
                "targetAmount": 500000.0,
                "currentAmount": 10000.0,
                "currency": "₹",
                "color": "#3344e6",
                "icon": "🚗",
                "createdAt": "2026-06-09T12:00:00Z",
                "updatedAt": "2026-06-09T12:00:00Z"
            }
        ]
        
        resp_put = client.put(f"/api/v1/auth/profile/{user_id}/goals", json=goals_payload)
        assert resp_put.status_code == 200
        assert resp_put.json()["status"] == "success"
        assert len(resp_put.json()["goals"]) == 1
        assert resp_put.json()["goals"][0]["name"] == "Save for a Car"
        
        # 4. Get profile again and check goals
        response_after = client.get(f"/api/v1/auth/profile/{user_id}")
        assert response_after.status_code == 200
        data_after = response_after.json()
        assert len(data_after["goals"]) == 1
        assert data_after["goals"][0]["id"] == "goal-1"
        assert data_after["goals"][0]["targetAmount"] == 500000.0
        
    finally:
        db_session.query(User).filter(User.id == user_id).delete()
        db_session.commit()
        db_session.close()
