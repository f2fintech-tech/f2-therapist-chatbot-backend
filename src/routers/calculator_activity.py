"""
Calculator Activity router — save and migrate user loan calculator activities.
"""
import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models import get_db, User, UserLoanCalculatorActivity, get_or_create_user
from src.utils.api_security import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calculator", tags=["Calculator Activity"], dependencies=[Depends(require_api_key)])


class SaveCalculatorActivityRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=36)
    calculator_type: str = Field(..., min_length=1, max_length=32)
    loan_type: str | None = Field(default=None, max_length=32)
    inputs: dict = Field(..., description="Key-value pairs of all input amounts filled in the tab")


class CalculatorActivityResponse(BaseModel):
    id: str
    user_id: str
    calculator_type: str
    loan_type: str | None
    inputs: dict
    created_at: datetime

    class Config:
        from_attributes = True


class MigrateCalculatorActivityRequest(BaseModel):
    from_user_id: str = Field(..., min_length=1, max_length=36)
    to_user_id: str = Field(..., min_length=1, max_length=36)


@router.post("/activity", response_model=CalculatorActivityResponse, status_code=status.HTTP_201_CREATED)
def save_calculator_activity(payload: SaveCalculatorActivityRequest, db: Session = Depends(get_db)):
    """Log a new calculator activity. Auto-creates guest user if they don't exist yet."""
    # Ensure user exists, or create as guest (to support instant guest computations)
    user = get_or_create_user(db, payload.user_id)

    activity = UserLoanCalculatorActivity(
        id=str(uuid.uuid4()),
        user_id=user.id,
        calculator_type=payload.calculator_type,
        loan_type=payload.loan_type,
        inputs=payload.inputs,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    logger.info(
        "Calculator activity logged: type=%s, loan_type=%s for user_id=%s",
        payload.calculator_type,
        payload.loan_type,
        user.id
    )
    return activity


@router.post("/migrate")
def migrate_calculator_activities(payload: MigrateCalculatorActivityRequest, db: Session = Depends(get_db)):
    """Migrate calculator activities from guest user to registered user on signup/login."""
    # Check if target user exists
    target_user = db.query(User).filter(User.id == payload.to_user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    updated_count = db.query(UserLoanCalculatorActivity).filter(
        UserLoanCalculatorActivity.user_id == payload.from_user_id
    ).update({"user_id": payload.to_user_id})
    db.commit()
    
    logger.info(
        "Migrated %d calculator activities from %s to %s",
        updated_count,
        payload.from_user_id,
        payload.to_user_id
    )
    return {"status": "ok", "migrated_count": updated_count}
