import os
import sys
import uuid

# Clear database environment variables to force fallback to local SQLite test.db
os.environ["DB_HOST"] = ""
os.environ["DB_USERNAME"] = ""
os.environ["DB_PASSWORD"] = ""
os.environ["DB_DATABASE"] = ""
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from src.main import app
from src.models import get_db, SessionLocal, Conversation

client = TestClient(app)

def test_rename_conversation():
    # 1. Create a user
    user_id = f"f2-test-{uuid.uuid4()}"
    db = SessionLocal()
    try:
        # Create a test conversation directly in DB
        conv_id = str(uuid.uuid4())
        conv = Conversation(
            id=conv_id,
            user_id=user_id,
            title="Initial Title"
        )
        db.add(conv)
        db.commit()
        
        print(f"Created conversation {conv_id} with title 'Initial Title'")
        
        # 2. Call the PUT endpoint to rename the conversation
        headers = {}
        # Check if API_ACCESS_TOKEN is configured in env
        expected_token = os.getenv("API_ACCESS_TOKEN", "").strip()
        if expected_token:
            headers["Authorization"] = f"Bearer {expected_token}"
            
        response = client.put(
            f"/api/v1/conversations/{conv_id}",
            params={"user_id": user_id},
            headers=headers,
            json={"title": "Updated Chat Title"}
        )
        
        print("PUT response status code:", response.status_code)
        print("PUT response body:", response.text)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Chat Title"
        
        # 3. Verify in DB
        db.refresh(conv)
        print(f"Conversation title in DB after update: '{conv.title}'")
        assert conv.title == "Updated Chat Title"
        print("SUCCESS: Rename conversation verified successfully!")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_rename_conversation()
