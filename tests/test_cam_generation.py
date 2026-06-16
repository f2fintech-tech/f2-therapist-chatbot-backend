import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models import get_db, User, Base, engine, UserCreditReport

client = TestClient(app)

def test_cam_generation_flow():
    # Create tables
    Base.metadata.create_all(bind=engine)
    db: Session = next(get_db())

    # Create dummy user and credit report with 7 active accounts
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"cam_test_{user_id[:8]}@example.com",
        name="Test CAM Customer",
        hearts=50,
        is_guest="false"
    )
    
    mock_accounts = [
        {"type": "Personal Loan", "lender": "SBI", "sanctioned_amount": 500000, "outstanding_balance": 450000, "emi": 12000, "open_date": "2025-08-20", "is_active": True},
        {"type": "Credit Card", "lender": "ICICI", "sanctioned_amount": 150000, "outstanding_balance": 45000, "emi": 3000, "open_date": "2026-01-01", "is_active": True},
        {"type": "Car Loan", "lender": "HDFC", "sanctioned_amount": 918998, "outstanding_balance": 540105, "emi": 19000, "open_date": "2025-01-10", "is_active": True},
        {"type": "Education Loan", "lender": "CANERA", "sanctioned_amount": 6750000, "outstanding_balance": 6650000, "emi": 0, "open_date": "2024-11-05", "is_active": True},
        {"type": "Business Loan", "lender": "HDFC", "sanctioned_amount": 285907, "outstanding_balance": 279991, "emi": 10000, "open_date": "2026-02-10", "is_active": True},
        {"type": "Home Loan", "lender": "CHOLA", "sanctioned_amount": 1519819, "outstanding_balance": 1519819, "emi": 40000, "open_date": "2026-03-12", "is_active": True},
        {"type": "Gold Loan", "lender": "AXIS", "sanctioned_amount": 200000, "outstanding_balance": 180000, "emi": 5000, "open_date": "2025-05-15", "is_active": True},
    ]
    
    report_data = {
        "score": 750,
        "band": "Excellent",
        "pan": "ABCDE1234F",
        "name": "Test CAM Customer",
        "phone": "9988775544",
        "metrics": {
            "payment_on_time_pct": 100,
            "credit_utilization_pct": 15,
            "credit_history_age_years": 4.5,
            "enquiries_l6m": 1,
            "secured_loans_count": 3,
            "unsecured_loans_count": 4,
            "write_offs": 0,
            "defaults": 0
        },
        "accounts": mock_accounts,
        "tips": ["Keep up the good work!"],
        "pdf_url": "http://example.com/report.pdf",
        "fetched_at": "2026-06-15T12:00:00Z"
    }

    credit_report = UserCreditReport(
        id=str(uuid.uuid4()),
        user_id=user_id,
        bureau="cibil",
        score=750,
        report_data=report_data,
        raw_bureau_json=None,
        pdf_url="http://example.com/report.pdf"
    )

    db.add(user)
    db.add(credit_report)
    db.commit()

    try:
        # Request CAM generation
        response = client.get(f"/api/v1/cibil/cam/generate/{user_id}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment; filename=CAM_Report_" in response.headers["content-disposition"]
        
        # Verify that we can parse the returned bytes as a zip file (which Excel is)
        import zipfile
        import io
        zip_buf = io.BytesIO(response.content)
        assert zipfile.is_zipfile(zip_buf)
        
        # Verify it contains sheet1.xml
        with zipfile.ZipFile(zip_buf) as z:
            assert 'xl/worksheets/sheet1.xml' in z.namelist()
            
    finally:
        # Cleanup database
        db.delete(credit_report)
        db.delete(user)
        db.commit()
        db.close()
