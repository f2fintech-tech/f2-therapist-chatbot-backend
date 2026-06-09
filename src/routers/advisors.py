from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
from src.models import Advisor, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisors", tags=["Advisors"])

class AdvisorBase(BaseModel):
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

class AdvisorCreate(AdvisorBase):
    f2_fintech_id: str

class AvailabilityUpdate(BaseModel):
    availability: str

class NextSlotUpdate(BaseModel):
    next_slot: str

@router.get("", response_model=List[AdvisorCreate])
async def get_advisors(db: Session = Depends(get_db)):
    """
    Fetch the list of all active advisor profiles from the database.
    """
    try:
        advisors = db.query(Advisor).all()
        # Map objects to matching schema output
        return [
            AdvisorCreate(
                f2_fintech_id=a.f2_fintech_id,
                name=a.name,
                designation=a.designation,
                avatar_url=a.avatar_url,
                availability=a.availability,
                expertise=a.expertise or [],
                strength=a.strength,
                bio=a.bio,
                rating=a.rating,
                reviews_count=a.reviews_count,
                next_slot=a.next_slot,
                category=a.category,
                fee=a.fee
            ) for a in advisors
        ]
    except Exception as e:
        logger.error(f"Error fetching advisors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch advisors: {str(e)}")

@router.post("", response_model=AdvisorCreate)
async def save_advisor(payload: AdvisorCreate, db: Session = Depends(get_db)):
    """
    Create a new advisor profile, or update it if f2_fintech_id already exists.
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
            target = existing
        else:
            # Create new
            new_advisor = Advisor(
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
            db.add(new_advisor)
            db.commit()
            db.refresh(new_advisor)
            target = new_advisor

        return AdvisorCreate(
            f2_fintech_id=target.f2_fintech_id,
            name=target.name,
            designation=target.designation,
            avatar_url=target.avatar_url,
            availability=target.availability,
            expertise=target.expertise or [],
            strength=target.strength,
            bio=target.bio,
            rating=target.rating,
            reviews_count=target.reviews_count,
            next_slot=target.next_slot,
            category=target.category,
            fee=target.fee
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving advisor: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save advisor: {str(e)}")

@router.delete("/{f2_fintech_id}", status_code=status.HTTP_200_OK)
async def delete_advisor(f2_fintech_id: str, db: Session = Depends(get_db)):
    """
    Remove an advisor profile from the database.
    """
    try:
        advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_fintech_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail="Advisor profile not found")
        db.delete(advisor)
        db.commit()
        return {"status": "success", "message": f"Advisor {f2_fintech_id} deleted successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting advisor: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete advisor: {str(e)}")

@router.put("/{f2_fintech_id}/availability", response_model=AdvisorCreate)
async def update_availability(f2_fintech_id: str, payload: AvailabilityUpdate, db: Session = Depends(get_db)):
    """
    Update live availability status for a specific advisor.
    """
    try:
        advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_fintech_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail="Advisor profile not found")
        
        advisor.availability = payload.availability
        db.commit()
        db.refresh(advisor)
        
        return AdvisorCreate(
            f2_fintech_id=advisor.f2_fintech_id,
            name=advisor.name,
            designation=advisor.designation,
            avatar_url=advisor.avatar_url,
            availability=advisor.availability,
            expertise=advisor.expertise or [],
            strength=advisor.strength,
            bio=advisor.bio,
            rating=advisor.rating,
            reviews_count=advisor.reviews_count,
            next_slot=advisor.next_slot,
            category=advisor.category,
            fee=advisor.fee
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating advisor availability: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update availability: {str(e)}")

@router.put("/{f2_fintech_id}/next-slot", response_model=AdvisorCreate)
async def update_next_slot(f2_fintech_id: str, payload: NextSlotUpdate, db: Session = Depends(get_db)):
    """
    Update the next available booking slot for a specific advisor.
    """
    try:
        advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_fintech_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail="Advisor profile not found")
        
        advisor.next_slot = payload.next_slot
        db.commit()
        db.refresh(advisor)
        
        return AdvisorCreate(
            f2_fintech_id=advisor.f2_fintech_id,
            name=advisor.name,
            designation=advisor.designation,
            avatar_url=advisor.avatar_url,
            availability=advisor.availability,
            expertise=advisor.expertise or [],
            strength=advisor.strength,
            bio=advisor.bio,
            rating=advisor.rating,
            reviews_count=advisor.reviews_count,
            next_slot=advisor.next_slot,
            category=advisor.category,
            fee=advisor.fee
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating advisor next-slot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update next-slot: {str(e)}")
