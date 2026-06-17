import uuid
import json
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models import get_db, User, Base, engine, Advisor, Conversation, ConversationMessage, MessageRole

client = TestClient(app)

def test_advisor_monthly_chat_limit():
    # Setup test tables in SQLite
    Base.metadata.create_all(bind=engine)
    db: Session = next(get_db())

    # Create an advisor in the database
    advisor_id = "f2-test-advisor-101"
    
    # Helper to clean up database state
    def cleanup():
        conv_ids = [c.id for c in db.query(Conversation).filter(Conversation.user_id == advisor_id).all()]
        if conv_ids:
            db.query(ConversationMessage).filter(ConversationMessage.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
        db.query(Conversation).filter(Conversation.user_id == advisor_id).delete(synchronize_session=False)
        db.query(Advisor).filter(Advisor.f2_fintech_id == advisor_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == advisor_id).delete(synchronize_session=False)
        db.commit()

    cleanup()

    # Create the advisor profile in the advisors table
    advisor_profile = Advisor(
        f2_fintech_id=advisor_id,
        name="Test Advisor",
        designation="Financial Consultant",
        category="Consultant"
    )
    db.add(advisor_profile)
    db.commit()

    # Define headers
    headers = {"Authorization": "Bearer dev_api_key"}

    try:
        # 1. Verify the advisor can chat under their f2- ID format
        payload = {
            "message": "Hello FinHeal, this is message 1",
            "user_id": advisor_id
        }
        
        response = client.post("/api/v1/chat/", json=payload, headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # 2. Add 9 more messages to database for this month to reach the limit of 10
        # Find the user created by get_or_create_user
        advisor_user = db.query(User).filter(User.id == advisor_id).first()
        assert advisor_user is not None
        
        # Find the conversation
        conversation = db.query(Conversation).filter(Conversation.user_id == advisor_id).first()
        assert conversation is not None
        
        # Insert 9 more messages sent by USER to simulate hitting the monthly limit
        for i in range(2, 11):
            msg = ConversationMessage(
                id=str(uuid.uuid4()),
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=f"Simulated message {i}",
                created_at=datetime.utcnow()
            )
            db.add(msg)
        db.commit()
        
        # 3. Try to send the 11th message - should be rejected with 403
        payload_11 = {
            "message": "This is message 11",
            "user_id": advisor_id,
            "conversation_id": conversation.id
        }
        response_11 = client.post("/api/v1/chat/", json=payload_11, headers=headers)
        assert response_11.status_code == 403, f"Expected 403, got {response_11.status_code}: {response_11.text}"
        
        # Validate the response detail message
        data = response_11.json()
        assert "Advisor monthly message limit reached" in data["detail"]

    finally:
        cleanup()
        db.close()
