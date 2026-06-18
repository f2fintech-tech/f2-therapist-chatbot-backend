import uuid
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models import (
    get_db, User, Base, engine, Conversation, ConversationMessage,
    MessageRole, UserCreditReport, UserLoanCalculatorActivity, UserSessionReport
)

client = TestClient(app)

def test_user_reports_pipeline():
    # Setup test tables in SQLite
    Base.metadata.create_all(bind=engine)
    db: Session = next(get_db())

    user_id = "test-user-reports-id"
    headers = {"Authorization": "Bearer dev_api_key"}

    # Cleanup helper
    def cleanup():
        db.query(UserSessionReport).filter(UserSessionReport.user_id == user_id).delete()
        db.query(UserLoanCalculatorActivity).filter(UserLoanCalculatorActivity.user_id == user_id).delete()
        db.query(UserCreditReport).filter(UserCreditReport.user_id == user_id).delete()
        convs = db.query(Conversation).filter(Conversation.user_id == user_id).all()
        for c in convs:
            db.query(ConversationMessage).filter(ConversationMessage.conversation_id == c.id).delete()
        db.query(Conversation).filter(Conversation.user_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()

    cleanup()

    try:
        # 1. Fetch reports for user when none exist - should return []
        resp = client.get(f"/api/v1/chat/reports/{user_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

        # 2. Try triggering daily report when user has NO activity - should return skipped status
        user_profile = User(
            id=user_id,
            name="Test User",
            hearts=50,
            is_guest="false",
            wellness_score=60,
            wellness_tier="Grower"
        )
        db.add(user_profile)
        db.commit()

        resp_trigger_empty = client.post(f"/api/v1/chat/reports/{user_id}/trigger?report_type=daily", headers=headers)
        assert resp_trigger_empty.status_code == 200
        assert resp_trigger_empty.json()["status"] == "skipped"

        # 3. Simulate user activity (chats, credit report, calculator run)
        # Create a conversation & messages
        conv = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title="Savings Plan"
        )
        db.add(conv)
        db.commit()

        user_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            role=MessageRole.USER,
            content="I want to improve my credit score",
            created_at=datetime.utcnow() - timedelta(hours=2)
        )
        db.add(user_msg)

        user_msg_past = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            role=MessageRole.USER,
            content="I am worried about my debts",
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.add(user_msg_past)

        assistant_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            role=MessageRole.ASSISTANT,
            content="You can do that by paying your credit cards on time.",
            created_at=datetime.utcnow() - timedelta(hours=2),
            mood={
                "dimensions": {
                    "stress": 30,
                    "urgency": 20,
                    "openness": 80,
                    "willingness": 90,
                    "emotion": 70
                }
            }
        )
        db.add(assistant_msg)

        # Create CIBIL report checker activity
        cibil = UserCreditReport(
            id=str(uuid.uuid4()),
            user_id=user_id,
            bureau="cibil",
            score=735,
            report_data={},
            fetched_at=datetime.utcnow() - timedelta(hours=1)
        )
        db.add(cibil)

        # Create Calculator activity
        calc = UserLoanCalculatorActivity(
            id=str(uuid.uuid4()),
            user_id=user_id,
            calculator_type="emi",
            loan_type="home",
            inputs={},
            created_at=datetime.utcnow() - timedelta(minutes=30)
        )
        db.add(calc)
        db.commit()

        # 4. Trigger report generation using mock LLM response
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "summary": "The user is actively focusing on improving their credit score. They checked their CIBIL score (735) and ran a home loan EMI calculator. They display low stress and a high willingness to adopt structured payment plans.",
            "key_takeaways": [
                "🎯 Pay card balances in full monthly.",
                "📊 Sync CIBIL checks every quarter.",
                "🏠 Keep EMI budget below 40% of income."
            ]
        })
        mock_llm.invoke.return_value = mock_response

        with patch("src.utils.report_worker.get_report_llm", return_value=mock_llm):
            resp_trigger = client.post(f"/api/v1/chat/reports/{user_id}/trigger?report_type=daily", headers=headers)
            assert resp_trigger.status_code == 200
            data = resp_trigger.json()
            assert data["status"] == "success"
            assert data["report"]["report_type"] == "daily"
            assert "CIBIL" in data["report"]["summary"]
            assert len(data["report"]["key_takeaways"]) == 3
            assert data["report"]["mood_trend"]["stress"] == 30.0
            assert data["report"]["activity_summary"]["cibil_checks"] == 1
            assert data["report"]["activity_summary"]["calculator_runs"] == 1

            # 5. Verify the report is saved and retrieved by the GET endpoint
            resp_list = client.get(f"/api/v1/chat/reports/{user_id}", headers=headers)
            assert resp_list.status_code == 200
            reports = resp_list.json()
            assert len(reports) == 3
            daily_report = next(r for r in reports if r["report_type"] == "daily")
            assert daily_report["key_takeaways"][0].startswith("🎯")

    finally:
        cleanup()
        db.close()
