from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Any
import logging

from src.models import get_db, Advisor
from src.utils.api_security import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisors", tags=["Advisors"], dependencies=[Depends(require_api_key)])


# ==================== Pydantic Schemas ====================

class AdvisorSchema(BaseModel):
    f2_fintech_id: str = Field(..., description="Unique F2 Fintech ID representing the advisor")
    name: str
    designation: str
    avatar_url: Optional[str] = None
    availability: str = "available"
    expertise: Optional[List[str]] = None
    strength: Optional[str] = None
    bio: Optional[str] = None
    rating: float = 4.8
    reviews_count: int = 15
    next_slot: Optional[str] = None
    category: str
    fee: int = 899

    class Config:
        orm_mode = True


class UpdateAvailabilityRequest(BaseModel):
    availability: str


class UpdateNextSlotRequest(BaseModel):
    next_slot: str


# ==================== Endpoints ====================

@router.get("", response_model=List[AdvisorSchema])
def get_advisors(db: Session = Depends(get_db)):
    """
    Fetch all active advisors.
    """
    try:
        return db.query(Advisor).all()
    except Exception as e:
        logger.error(f"Error fetching advisors: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch advisors: {str(e)}"
        )


@router.post("", response_model=AdvisorSchema)
def save_advisor(payload: AdvisorSchema, db: Session = Depends(get_db)):
    """
    Create a new advisor or update an existing advisor profile using f2_fintech_id.
    """
    try:
        existing = db.query(Advisor).filter(Advisor.f2_fintech_id == payload.f2_fintech_id).first()
        if existing:
            # Update fields
            existing.name = payload.name
            existing.designation = payload.designation
            existing.avatar_url = payload.avatar_url
            existing.availability = payload.availability
            existing.expertise = payload.expertise
            existing.strength = payload.strength
            existing.bio = payload.bio
            existing.rating = payload.rating
            existing.reviews_count = payload.reviews_count
            existing.next_slot = payload.next_slot
            existing.category = payload.category
            existing.fee = payload.fee
            db.commit()
            db.refresh(existing)
            logger.info(f"Updated advisor profile: {payload.f2_fintech_id}")
            return existing
        else:
            # Create new
            new_adv = Advisor(
                f2_fintech_id=payload.f2_fintech_id,
                name=payload.name,
                designation=payload.designation,
                avatar_url=payload.avatar_url,
                availability=payload.availability,
                expertise=payload.expertise,
                strength=payload.strength,
                bio=payload.bio,
                rating=payload.rating,
                reviews_count=payload.reviews_count,
                next_slot=payload.next_slot,
                category=payload.category,
                fee=payload.fee
            )
            db.add(new_adv)
            db.commit()
            db.refresh(new_adv)
            logger.info(f"Created new advisor profile: {payload.f2_fintech_id}")
            return new_adv
    except Exception as e:
        logger.error(f"Error saving advisor: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save advisor: {str(e)}"
        )


@router.delete("/{f2_fintech_id}", status_code=status.HTTP_200_OK)
def delete_advisor(f2_fintech_id: str, db: Session = Depends(get_db)):
    """
    Remove an advisor profile.
    """
    try:
        adv = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_fintech_id).first()
        if not adv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Advisor with F2 Fintech ID {f2_fintech_id} not found."
            )
        db.delete(adv)
        db.commit()
        logger.info(f"Deleted advisor profile: {f2_fintech_id}")
        return {"status": "success", "message": f"Deleted advisor with F2 Fintech ID {f2_fintech_id}"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting advisor: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete advisor: {str(e)}"
        )


@router.put("/{f2_fintech_id}/availability", response_model=AdvisorSchema)
def update_availability(f2_fintech_id: str, payload: UpdateAvailabilityRequest, db: Session = Depends(get_db)):
    """
    Quickly update advisor availability status.
    """
    try:
        adv = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_fintech_id).first()
        if not adv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Advisor with F2 Fintech ID {f2_fintech_id} not found."
            )
        adv.availability = payload.availability
        db.commit()
        db.refresh(adv)
        logger.info(f"Updated advisor availability for {f2_fintech_id} to {payload.availability}")
        return adv
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating availability: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update availability: {str(e)}"
        )


@router.put("/{f2_fintech_id}/next-slot", response_model=AdvisorSchema)
def update_next_slot(f2_fintech_id: str, payload: UpdateNextSlotRequest, db: Session = Depends(get_db)):
    """
    Quickly update advisor next slot scheduling information.
    """
    try:
        adv = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_fintech_id).first()
        if not adv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Advisor with F2 Fintech ID {f2_fintech_id} not found."
            )
        adv.next_slot = payload.next_slot
        db.commit()
        db.refresh(adv)
        logger.info(f"Updated advisor next slot for {f2_fintech_id} to {payload.next_slot}")
        return adv
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating next slot: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update next slot: {str(e)}"
        )
