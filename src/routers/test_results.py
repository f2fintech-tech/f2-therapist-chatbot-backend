"""
Test Results router — save and retrieve financial test results per user.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import logging

from src.models import get_db, TestResult, User
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


@router.post("/", response_model=TestResultResponse, status_code=status.HTTP_201_CREATED)
def save_test_result(payload: SaveTestResultRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = TestResult(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        test_type=payload.test_type,
        score=payload.score,
        percentage_score=payload.percentage_score,
        risk_level=payload.risk_level,
        category=payload.category,
        result_data=payload.result_data,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    logger.info("Test result saved: %s for user %s", payload.test_type, payload.user_id)
    return result


@router.get("/{user_id}", response_model=list[TestResultResponse])
def get_test_results(user_id: str, db: Session = Depends(get_db)):
    results = db.query(TestResult).filter(
        TestResult.user_id == user_id
    ).order_by(TestResult.completed_at.desc()).all()
    return results


class MigrateTestResultsRequest(BaseModel):
    from_user_id: str
    to_user_id: str


@router.post("/migrate")
def migrate_test_results(payload: MigrateTestResultsRequest, db: Session = Depends(get_db)):
    """Migrate test results from guest user to real user on signup/login."""
    db.query(TestResult).filter(
        TestResult.user_id == payload.from_user_id
    ).update({"user_id": payload.to_user_id})
    db.commit()
    logger.info("Migrated test results from %s to %s", payload.from_user_id, payload.to_user_id)
    return {"status": "ok"}
