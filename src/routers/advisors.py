from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
import os
import shutil
from src.models import Advisor, AdvisorAppointment, get_db

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


@router.post("/{f2_fintech_id}/upload-avatar")
async def upload_avatar(
    f2_fintech_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a local profile image for an advisor and update their avatar_url in the database.
    """
    try:
        advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_fintech_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail="Advisor profile not found")
        
        # Validate file type
        content_type = file.content_type
        if not content_type or not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Uploaded file is not an image")
        
        # Save to static directory as {f2_fintech_id}.png
        target_dir = os.path.join("src", "static", "avatars")
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, f"{f2_fintech_id}.png")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Build the dynamic URL.
        base_url = str(request.base_url).rstrip("/")
        avatar_url = f"{base_url}/static/avatars/{f2_fintech_id}.png"
        
        # Update advisor
        advisor.avatar_url = avatar_url
        db.commit()
        db.refresh(advisor)
        
        return {"status": "success", "avatar_url": avatar_url}
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading avatar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload avatar: {str(e)}")


# ==================== Advisor Appointments Endpoints ====================

class AppointmentCreate(BaseModel):
    user_id: str
    advisor_id: str
    advisor_name: str
    date: str
    time: str
    notes: Optional[str] = None
    meet_url: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: str
    user_id: str
    advisor_id: str
    advisor_name: str
    date: str
    time: str
    notes: Optional[str] = None
    booked_at: str
    completed: bool
    cancelled: bool
    rating: Optional[int] = None
    feedback: Optional[str] = None
    meet_url: Optional[str] = None
    joined: bool

class AppointmentStatusUpdate(BaseModel):
    completed: Optional[bool] = None
    cancelled: Optional[bool] = None
    rating: Optional[int] = None
    feedback: Optional[str] = None

@router.post("/appointments", response_model=AppointmentResponse)
async def book_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    import uuid
    from datetime import datetime
    try:
        # Check if advisor exists
        advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == payload.advisor_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail="Advisor profile not found")
        
        appt_id = str(uuid.uuid4())
        new_appt = AdvisorAppointment(
            id=appt_id,
            user_id=payload.user_id,
            advisor_id=payload.advisor_id,
            advisor_name=payload.advisor_name,
            date=payload.date,
            time=payload.time,
            notes=payload.notes,
            meet_url=payload.meet_url,
            booked_at=datetime.utcnow(),
            completed=False,
            cancelled=False,
            joined=False
        )
        db.add(new_appt)
        db.commit()
        db.refresh(new_appt)
        return AppointmentResponse(
            id=new_appt.id,
            user_id=new_appt.user_id,
            advisor_id=new_appt.advisor_id,
            advisor_name=new_appt.advisor_name,
            date=new_appt.date,
            time=new_appt.time,
            notes=new_appt.notes,
            booked_at=new_appt.booked_at.isoformat(),
            completed=new_appt.completed,
            cancelled=new_appt.cancelled,
            rating=new_appt.rating,
            feedback=new_appt.feedback,
            meet_url=new_appt.meet_url,
            joined=new_appt.joined
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error booking appointment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to book appointment: {str(e)}")

@router.get("/appointments/user/{user_id}", response_model=List[AppointmentResponse])
async def get_user_appointments(user_id: str, db: Session = Depends(get_db)):
    try:
        appts = db.query(AdvisorAppointment).filter(AdvisorAppointment.user_id == user_id).order_by(AdvisorAppointment.booked_at.desc()).all()
        return [
            AppointmentResponse(
                id=a.id,
                user_id=a.user_id,
                advisor_id=a.advisor_id,
                advisor_name=a.advisor_name,
                date=a.date,
                time=a.time,
                notes=a.notes,
                booked_at=a.booked_at.isoformat(),
                completed=a.completed,
                cancelled=a.cancelled,
                rating=a.rating,
                feedback=a.feedback,
                meet_url=a.meet_url,
                joined=a.joined
            ) for a in appts
        ]
    except Exception as e:
        logger.error(f"Error fetching user appointments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch user appointments: {str(e)}")

@router.get("/appointments/advisor/{advisor_id}", response_model=List[AppointmentResponse])
async def get_advisor_appointments(advisor_id: str, db: Session = Depends(get_db)):
    try:
        appts = db.query(AdvisorAppointment).filter(AdvisorAppointment.advisor_id == advisor_id).order_by(AdvisorAppointment.booked_at.desc()).all()
        return [
            AppointmentResponse(
                id=a.id,
                user_id=a.user_id,
                advisor_id=a.advisor_id,
                advisor_name=a.advisor_name,
                date=a.date,
                time=a.time,
                notes=a.notes,
                booked_at=a.booked_at.isoformat(),
                completed=a.completed,
                cancelled=a.cancelled,
                rating=a.rating,
                feedback=a.feedback,
                meet_url=a.meet_url,
                joined=a.joined
            ) for a in appts
        ]
    except Exception as e:
        logger.error(f"Error fetching advisor appointments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch advisor appointments: {str(e)}")

@router.get("/appointments/all", response_model=List[AppointmentResponse])
async def get_all_appointments(db: Session = Depends(get_db)):
    try:
        appts = db.query(AdvisorAppointment).order_by(AdvisorAppointment.booked_at.desc()).all()
        return [
            AppointmentResponse(
                id=a.id,
                user_id=a.user_id,
                advisor_id=a.advisor_id,
                advisor_name=a.advisor_name,
                date=a.date,
                time=a.time,
                notes=a.notes,
                booked_at=a.booked_at.isoformat(),
                completed=a.completed,
                cancelled=a.cancelled,
                rating=a.rating,
                feedback=a.feedback,
                meet_url=a.meet_url,
                joined=a.joined
            ) for a in appts
        ]
    except Exception as e:
        logger.error(f"Error fetching all appointments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch all appointments: {str(e)}")

@router.put("/appointments/{appt_id}/status", response_model=AppointmentResponse)
async def update_appointment_status(appt_id: str, payload: AppointmentStatusUpdate, db: Session = Depends(get_db)):
    try:
        appt = db.query(AdvisorAppointment).filter(AdvisorAppointment.id == appt_id).first()
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        if payload.completed is not None:
            appt.completed = payload.completed
        if payload.cancelled is not None:
            appt.cancelled = payload.cancelled
        if payload.rating is not None:
            appt.rating = payload.rating
        if payload.feedback is not None:
            appt.feedback = payload.feedback
            
        db.commit()
        db.refresh(appt)
        return AppointmentResponse(
            id=appt.id,
            user_id=appt.user_id,
            advisor_id=appt.advisor_id,
            advisor_name=appt.advisor_name,
            date=appt.date,
            time=appt.time,
            notes=appt.notes,
            booked_at=appt.booked_at.isoformat(),
            completed=appt.completed,
            cancelled=appt.cancelled,
            rating=appt.rating,
            feedback=appt.feedback,
            meet_url=appt.meet_url,
            joined=appt.joined
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating appointment status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update appointment status: {str(e)}")

@router.put("/appointments/{appt_id}/join", response_model=AppointmentResponse)
async def join_appointment(appt_id: str, db: Session = Depends(get_db)):
    try:
        appt = db.query(AdvisorAppointment).filter(AdvisorAppointment.id == appt_id).first()
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        appt.joined = True
        db.commit()
        db.refresh(appt)
        return AppointmentResponse(
            id=appt.id,
            user_id=appt.user_id,
            advisor_id=appt.advisor_id,
            advisor_name=appt.advisor_name,
            date=appt.date,
            time=appt.time,
            notes=appt.notes,
            booked_at=appt.booked_at.isoformat(),
            completed=appt.completed,
            cancelled=appt.cancelled,
            rating=appt.rating,
            feedback=appt.feedback,
            meet_url=appt.meet_url,
            joined=appt.joined
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error joining appointment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to mark appointment joined: {str(e)}")

class AppointmentReschedule(BaseModel):
    date: str
    time: str

@router.put("/appointments/{appt_id}/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(appt_id: str, payload: AppointmentReschedule, db: Session = Depends(get_db)):
    try:
        appt = db.query(AdvisorAppointment).filter(AdvisorAppointment.id == appt_id).first()
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if appt.cancelled:
            raise HTTPException(status_code=400, detail="Cannot reschedule a cancelled appointment")
        if appt.completed:
            raise HTTPException(status_code=400, detail="Cannot reschedule a completed appointment")
        
        appt.date = payload.date
        appt.time = payload.time
        db.commit()
        db.refresh(appt)
        return AppointmentResponse(
            id=appt.id,
            user_id=appt.user_id,
            advisor_id=appt.advisor_id,
            advisor_name=appt.advisor_name,
            date=appt.date,
            time=appt.time,
            notes=appt.notes,
            booked_at=appt.booked_at.isoformat(),
            completed=appt.completed,
            cancelled=appt.cancelled,
            rating=appt.rating,
            feedback=appt.feedback,
            meet_url=appt.meet_url,
            joined=appt.joined
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error rescheduling appointment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reschedule appointment: {str(e)}")
