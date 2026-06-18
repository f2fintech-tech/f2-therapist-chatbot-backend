"""
Test Results router — save and retrieve financial test results per user.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import logging

from src.models import get_db, TestResult, User, UserCreditReport, UserConsolidatedProfile
from src.utils.api_security import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test-results", tags=["Test Results"], dependencies=[Depends(require_api_key)])


class SaveTestResultRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=36)
    test_type: str = Field(..., min_length=1, max_length=100)
    score: int | None = None
    percentage_score: int | None = None
    risk_level: str | None = None
    category: str | None = None
    result_data: dict | None = None


class TestResultResponse(BaseModel):
    id: str
    user_id: str
    test_type: str
    score: int | None = None
    percentage_score: int | None = None
    risk_level: str | None = None
    category: str | None = None
    result_data: dict | None = None
    completed_at: datetime

    class Config:
        from_attributes = True


def map_db_to_response(r: TestResult) -> TestResultResponse:
    cb = r.category_breakdown or {}
    
    score = cb.get("score")
    if score is None:
        score = int(r.raw_score) if r.raw_score is not None else None
        
    percentage_score = cb.get("percentage_score")
    if percentage_score is None:
        percentage_score = int(r.normalized_score) if r.normalized_score is not None else None
        
    risk_level = cb.get("risk_level") or cb.get("risk")
    category = cb.get("category")
    result_data = cb.get("result_data") or cb
    
    return TestResultResponse(
        id=r.id,
        user_id=r.user_id,
        test_type=r.test_type,
        score=score,
        percentage_score=percentage_score,
        risk_level=risk_level,
        category=category,
        result_data=result_data,
        completed_at=r.completed_at
    )


@router.post("/", response_model=TestResultResponse, status_code=status.HTTP_201_CREATED)
def save_test_result(payload: SaveTestResultRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = TestResult(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        test_type=payload.test_type,
        raw_score=float(payload.score or payload.percentage_score or 0),
        normalized_score=float(payload.percentage_score or payload.score or 0),
        completed_at=datetime.utcnow(),
        insights=[],
        category_breakdown={
            "score": payload.score,
            "percentage_score": payload.percentage_score,
            "risk_level": payload.risk_level,
            "category": payload.category,
            "result_data": payload.result_data
        }
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    logger.info("Test result saved: %s for user %s", payload.test_type, payload.user_id)
    return map_db_to_response(result)


@router.get("/{user_id}", response_model=list[TestResultResponse])
def get_test_results(user_id: str, db: Session = Depends(get_db)):
    results = db.query(TestResult).filter(
        TestResult.user_id == user_id
    ).order_by(TestResult.completed_at.desc()).all()
    return [map_db_to_response(r) for r in results]


class MigrateTestResultsRequest(BaseModel):
    from_user_id: str
    to_user_id: str


@router.post("/migrate")
def migrate_test_results(payload: MigrateTestResultsRequest, db: Session = Depends(get_db)):
    """Migrate test results and associated credit reports and profile data from guest user to real user on signup/login."""
    # 1. Migrate test results
    db.query(TestResult).filter(
        TestResult.user_id == payload.from_user_id
    ).update({"user_id": payload.to_user_id})
    
    # 2. Migrate credit reports
    db.query(UserCreditReport).filter(
        UserCreditReport.user_id == payload.from_user_id
    ).update({"user_id": payload.to_user_id})
    
    # 3. Migrate/merge consolidated profile
    guest_profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == payload.from_user_id).first()
    if guest_profile:
        dest_profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == payload.to_user_id).first()
        if not dest_profile:
            guest_profile.user_id = payload.to_user_id
        else:
            if dest_profile.data is None:
                dest_profile.data = {}
            if guest_profile.data:
                for k, v in guest_profile.data.items():
                    if k not in dest_profile.data:
                        dest_profile.data[k] = v
                flag_modified(dest_profile, "data")
            db.delete(guest_profile)
            
    db.commit()
    logger.info("Migrated test results, credit reports, and profile from %s to %s", payload.from_user_id, payload.to_user_id)
    return {"status": "ok"}

