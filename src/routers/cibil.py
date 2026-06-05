import re
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, Field
from typing import Dict, Any, List

from src.models import get_db, User, UserConsolidatedProfile
from src.utils.api_security import require_api_key
from src.utils.cibil_client import fetch_actual_cibil_report
from src.utils.wellness_service import record_test_result
from src.routers.user_profile import get_or_create_consolidated_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cibil", tags=["CIBIL Analyzer"], dependencies=[Depends(require_api_key)])

# ==================== Pydantic Schemas ====================

class CibilFetchRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user requesting CIBIL fetch")
    name: str = Field(..., min_length=2, max_length=100, description="Full Name of the user")
    phone: str = Field(..., description="10-digit mobile number")
    pan: str = Field(..., description="10-character PAN Card number")

class CibilReportResponse(BaseModel):
    score: int
    band: str
    pan: str
    name: str
    phone: str
    metrics: Dict[str, Any]
    accounts: List[Dict[str, Any]]
    tips: List[str]
    fetched_at: str

# ==================== Router Endpoints ====================

@router.post("/fetch", response_model=CibilReportResponse)
async def fetch_cibil(payload: CibilFetchRequest, db: Session = Depends(get_db)):
    """
    Fetch the user's CIBIL credit report from the external API (or fallback simulation).
    Saves the report to Amazon RDS PostgreSQL and records a credit health test result to update the wellness score.
    """
    user_id = payload.user_id
    name = payload.name.strip()
    phone = payload.phone.strip()
    pan = payload.pan.upper().strip()

    # 1. Input Validations
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User session not found in the database."
        )

    # Validate phone (digits only, length 10 or with country code)
    clean_phone = re.sub(r"\D", "", phone)
    if len(clean_phone) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid mobile number. Please enter a valid 10-digit number."
        )
    # Get last 10 digits
    clean_phone = clean_phone[-10:]

    # Validate PAN (5 letters, 4 digits, 1 letter)
    if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", pan):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid PAN Card format. Standard format is ABCDE1234F."
        )

    # 2. Fetch CIBIL Report
    try:
        report = await fetch_actual_cibil_report(name=name, phone=clean_phone, pan=pan)
    except Exception as e:
        logger.error(f"Error fetching CIBIL report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve credit score from CIBIL bureau. Please try again later."
        )

    score = report["score"]
    band = report["band"]
    tips = report["tips"]

    # 3. Update User Record Details
    user.phone = clean_phone
    if user.name == "Guest" or not user.name:
         user.name = name
    db.flush()

    # 4. Save CIBIL Report to Consolidated JSON Profile
    profile = get_or_create_consolidated_profile(db, user_id)
    profile_data = dict(profile.data or {})
    
    profile_data["cibil_report"] = report
    profile.data = profile_data
    flag_modified(profile, "data")
    db.flush()

    # 5. Update Wellness Score (Credit Health Pillar)
    # CIBIL Score is 300 to 900. Normalize to a 0-100 raw score for credit readiness test.
    normalized_credit_score = float((score - 300) / 6.0) # (900-300)/6 = 100
    
    try:
        record_test_result(
            session=db,
            user_id=user_id,
            test_type="credit_readiness",
            raw_score=normalized_credit_score,
            normalized_score=normalized_credit_score,
            insights=tips,
            category_breakdown={
                "cibil_score": score,
                "band": band,
                "utilization": report["metrics"]["credit_utilization_pct"],
                "on_time_payments": report["metrics"]["payment_on_time_pct"]
            }
        )
    except Exception as e:
        logger.error(f"Error logging credit test result: {e}", exc_info=True)
        # Non-fatal error, do not rollback fetch transaction
        pass

    db.commit()
    logger.info(f"CIBIL score {score} fetched and saved for user {user_id}")
    return report

@router.get("/report/{user_id}", response_model=Dict[str, Any])
def get_cibil_report(user_id: str, db: Session = Depends(get_db)):
    """
    Retrieve the user's stored CIBIL report from Amazon RDS PostgreSQL.
    """
    profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == user_id).first()
    if not profile or not profile.data or "cibil_report" not in profile.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CIBIL report found. Please fetch your credit report first."
        )
    
    return profile.data["cibil_report"]
