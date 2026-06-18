import uuid
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models import get_db, User, Base, engine, UserCreditReport, Advisor

client = TestClient(app)

def test_cibil_rate_limiting_flow(monkeypatch):
    from src.utils.cibil_client import generate_mock_report

    async def mock_cibil(name: str, phone: str, pan: str, is_company: bool = False):
        return generate_mock_report(name, phone, pan, is_company)

    async def mock_experian(name: str, phone: str, pan: str, is_company: bool = False):
        return generate_mock_report(name, phone, pan, is_company)

    monkeypatch.setattr("src.routers.cibil.fetch_actual_cibil_report", mock_cibil)
    monkeypatch.setattr("src.routers.cibil.fetch_actual_experian_report", mock_experian)

    # Create all tables in SQLite
    Base.metadata.create_all(bind=engine)
    db: Session = next(get_db())

    # Create users
    standard_user_id = str(uuid.uuid4())
    advisor_user_id = str(uuid.uuid4())
    admin_user_id = str(uuid.uuid4())

    standard_user = User(
        id=standard_user_id,
        email=f"client_{standard_user_id[:8]}@example.com",
        name="John Client",
        hearts=50,
        is_guest="false"
    )
    
    advisor_user = User(
        id=advisor_user_id,
        email="advisor_agent@f2fintech.com", # f2fintech.com domain
        name="Advisor Agent",
        hearts=50,
        is_guest="false"
    )

    admin_user = User(
        id=admin_user_id,
        email="admin@finheal.com", # admin email
        name="System Admin",
        hearts=50,
        is_guest="false"
    )

    # Add advisor user explicitly to advisors table
    advisor_profile = Advisor(
        f2_fintech_id=advisor_user_id,
        name="Advisor Agent",
        designation="Senior Credit Advisor",
        category="Credit"
    )

    db.add_all([standard_user, advisor_user, admin_user, advisor_profile])
    db.commit()

    headers = {"Authorization": "Bearer dev_api_key"} # mock auth / dependancy require_api_key uses config headers
    # Wait, the router depends on require_api_key. Let's see if we need a specific token or if we bypass it.
    # In tests/test_goals.py, does it pass any header? No!
    # Wait, in src/routers/cibil.py, router = APIRouter(prefix="/cibil", dependencies=[Depends(require_api_key)])
    # Let's check require_api_key in src/utils/api_security.py.

    try:
        # 1. Standard user first fetch - should succeed (using mock / fallback fetch)
        payload_1 = {
            "user_id": standard_user_id,
            "name": "John Client",
            "phone": "9876543210",
            "pan": "ABCDE1234F",
            "bureau": "cibil",
            "report_type": "individual"
        }
        
        response_1 = client.post("/api/v1/cibil/fetch", json=payload_1)
        # If API authentication is required and fail, let's look at the status code.
        # In src/utils/api_security.py, require_api_key might check API key in headers.
        # Let's inspect test_api_integration.py or similar to see if headers are needed.
        # If we get 401 or 403, we will add appropriate headers.
        
        # Let's assert success or handle require_api_key header
        if response_1.status_code == 401:
            # Let's try passing API Key header. In config: VITE_API_KEY / API_ACCESS_TOKEN
            # The test conftest or setup might configure API_ACCESS_TOKEN.
            import os
            api_token = os.getenv("API_ACCESS_TOKEN", "dev_api_key")
            auth_headers = {"Authorization": f"Bearer {api_token}"}
            response_1 = client.post("/api/v1/cibil/fetch", json=payload_1, headers=auth_headers)
            
        assert response_1.status_code == 200, f"Expected 200, got {response_1.status_code}: {response_1.text}"
        data_1 = response_1.json()
        assert "score" in data_1
        
        # 2. Standard user second fetch immediately - should return 429 Too Many Requests
        response_2 = client.post("/api/v1/cibil/fetch", json=payload_1, headers=auth_headers if 'auth_headers' in locals() else None)
        assert response_2.status_code == 429, f"Expected 429 for second fetch, got {response_2.status_code}: {response_2.text}"
        data_2 = response_2.json()
        assert "message" in data_2["detail"]
        assert "days_remaining" in data_2["detail"]

        # 3. Advisor user first fetch - should succeed
        payload_advisor = {
            "user_id": advisor_user_id,
            "name": "Advisor Agent",
            "phone": "9876543210",
            "pan": "ABCDE1234G",
            "bureau": "cibil",
            "report_type": "individual"
        }
        response_adv_1 = client.post("/api/v1/cibil/fetch", json=payload_advisor, headers=auth_headers if 'auth_headers' in locals() else None)
        assert response_adv_1.status_code == 200
        
        # 4. Advisor user second fetch - should ALSO succeed (exempt)
        response_adv_2 = client.post("/api/v1/cibil/fetch", json=payload_advisor, headers=auth_headers if 'auth_headers' in locals() else None)
        assert response_adv_2.status_code == 200

        # 5. Admin user first fetch - should succeed
        payload_admin = {
            "user_id": admin_user_id,
            "name": "System Admin",
            "phone": "9876543210",
            "pan": "ABCDE1234H",
            "bureau": "cibil",
            "report_type": "individual"
        }
        response_adm_1 = client.post("/api/v1/cibil/fetch", json=payload_admin, headers=auth_headers if 'auth_headers' in locals() else None)
        assert response_adm_1.status_code == 200
        
        # 6. Admin user second fetch - should ALSO succeed (exempt)
        response_adm_2 = client.post("/api/v1/cibil/fetch", json=payload_admin, headers=auth_headers if 'auth_headers' in locals() else None)
        assert response_adm_2.status_code == 200

        # 7. Experian fetch without PAN card - should succeed (using mock / fallback fetch)
        payload_experian = {
            "user_id": admin_user_id,
            "name": "John Client",
            "phone": "9876543210",
            "bureau": "experian",
            "report_type": "individual"
        }
        response_exp = client.post("/api/v1/cibil/fetch", json=payload_experian, headers=auth_headers if 'auth_headers' in locals() else None)
        assert response_exp.status_code == 200, f"Expected 200 for Experian fetch, got {response_exp.status_code}: {response_exp.text}"
        data_exp = response_exp.json()
        assert "score" in data_exp
        assert data_exp["pan"] == ""  # pan should default to empty string

    finally:
        # Cleanup
        db.query(UserCreditReport).filter(UserCreditReport.user_id.in_([standard_user_id, advisor_user_id, admin_user_id])).delete(synchronize_session=False)
        db.query(Advisor).filter(Advisor.f2_fintech_id == advisor_user_id).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_([standard_user_id, advisor_user_id, admin_user_id])).delete(synchronize_session=False)
        db.commit()
        db.close()
