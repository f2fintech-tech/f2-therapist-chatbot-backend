from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
import os
import shutil
import uuid
from datetime import datetime, timedelta
import secrets
from src.models import Advisor, AdvisorAppointment, User, get_db, ReferralCode

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
    rating: float = 0.0
    reviews_count: int = 0
    next_slot: Optional[str] = None
    category: str
    fee: int = 899
    original_fee: Optional[int] = None
    discount_expires_at: Optional[str] = None

class AdvisorCreate(AdvisorBase):
    f2_fintech_id: str
    test_comment: Optional[str] = None
    test_rating: Optional[int] = None

class AvailabilityUpdate(BaseModel):
    availability: str

class NextSlotUpdate(BaseModel):
    next_slot: str

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)



@router.get("", response_model=List[AdvisorCreate])
async def get_advisors(user_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Fetch the list of all active advisor profiles from the database.
    Applies a 50% discount if the user was referred.
    """
    try:
        advisors = db.query(Advisor).all()
        
        user_is_referred = False
        discount_expires_at = None
        if user_id:
            ref = db.query(ReferralCode).filter(ReferralCode.referred_user_id == user_id).first()
            if ref and ref.used_at:
                expires_date = ref.used_at + timedelta(days=15)
                if datetime.utcnow() < expires_date:
                    user_is_referred = True
                    discount_expires_at = expires_date.isoformat() + "Z"

        result = []
        for a in advisors:
            fee = a.fee
            original_fee = None
            adv_discount_expires = None
            if user_is_referred:
                original_fee = fee
                fee = int(fee * 0.5)
                adv_discount_expires = discount_expires_at

            result.append(
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
                    fee=fee,
                    original_fee=original_fee,
                    discount_expires_at=adv_discount_expires
                )
            )
        return result
    except Exception as e:
        logger.error(f"Error fetching advisors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch advisors: {str(e)}")

# ==================== Referral Endpoints ====================

class ReferralCodeResponse(BaseModel):
    id: str
    code: str
    status: str
    expires_at: str
    created_at: str
    used_at: Optional[str] = None

@router.post("/{f2_fintech_id}/referrals", response_model=ReferralCodeResponse)
async def generate_referral(f2_fintech_id: str, db: Session = Depends(get_db)):
    advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_fintech_id).first()
    if not advisor:
        raise HTTPException(status_code=404, detail="Advisor profile not found")
        
    code = secrets.token_hex(4).upper() # 8 char code
    ref = ReferralCode(
        id=str(uuid.uuid4()),
        advisor_id=f2_fintech_id,
        code=code,
        status="pending",
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)
    
    return ReferralCodeResponse(
        id=ref.id,
        code=ref.code,
        status=ref.status,
        expires_at=ref.expires_at.isoformat(),
        created_at=ref.created_at.isoformat(),
        used_at=ref.used_at.isoformat() if ref.used_at else None
    )

@router.get("/{f2_fintech_id}/referrals", response_model=List[ReferralCodeResponse])
async def list_referrals(f2_fintech_id: str, db: Session = Depends(get_db)):
    refs = db.query(ReferralCode).filter(ReferralCode.advisor_id == f2_fintech_id).order_by(ReferralCode.created_at.desc()).all()
    return [
        ReferralCodeResponse(
            id=r.id,
            code=r.code,
            status=r.status,
            expires_at=r.expires_at.isoformat(),
            created_at=r.created_at.isoformat(),
            used_at=r.used_at.isoformat() if r.used_at else None
        ) for r in refs
    ]


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

        # Check if a test review comment is provided to generate a simulated completed appointment
        if payload.test_comment and payload.test_comment.strip():
            from datetime import datetime, timedelta
            import uuid
            from src.models import User
            
            # Prevent double-click duplicates: check if the last completed review is identical and within 10 seconds
            last_appt = db.query(AdvisorAppointment).filter(
                AdvisorAppointment.advisor_id == target.f2_fintech_id,
                AdvisorAppointment.completed == True,
                AdvisorAppointment.feedback == payload.test_comment.strip()
            ).order_by(AdvisorAppointment.booked_at.desc()).first()

            is_duplicate = False
            if last_appt and (datetime.utcnow() - last_appt.booked_at) < timedelta(seconds=10):
                is_duplicate = True

            if not is_duplicate:
                # Find a user to link the appointment
                user = db.query(User).filter(User.email == "admin@f2finheal.com").first()
                if not user:
                    user = db.query(User).first()
                user_id = user.id if user else "test-user-id"

                # Determine mock rating to set
                simulated_rating = payload.test_rating if payload.test_rating else 5
                if simulated_rating < 1:
                    simulated_rating = 1
                elif simulated_rating > 5:
                    simulated_rating = 5

                new_appt = AdvisorAppointment(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    advisor_id=target.f2_fintech_id,
                    advisor_name=target.name,
                    date="Today",
                    time="12:00 PM",
                    notes="Simulated test review from Admin Portal",
                    completed=True,
                    cancelled=False,
                    rating=simulated_rating,
                    feedback=payload.test_comment.strip(),
                    meet_url="https://meet.google.com/test-meet"
                )
                db.add(new_appt)
                db.commit()

                # Recalculate stats dynamically
                update_advisor_rating_stats(target.f2_fintech_id, db)
                db.refresh(target)

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
            fee=target.fee,
            test_comment=payload.test_comment,
            test_rating=payload.test_rating
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

@router.put("/{f2_fintech_id}/password", status_code=status.HTTP_200_OK)
async def update_password(f2_fintech_id: str, payload: PasswordUpdate, db: Session = Depends(get_db)):
    """
    Update the login password for an advisor.
    """
    try:
        advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_fintech_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail="Advisor profile not found")
        
        # Verify current password
        if advisor.password_hash:
            import bcrypt as _bcrypt
            if not _bcrypt.checkpw(payload.current_password.encode(), advisor.password_hash.encode()):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Current password is incorrect"
                )
        
        import bcrypt as _bcrypt
        hashed = _bcrypt.hashpw(payload.new_password.encode(), _bcrypt.gensalt()).decode()
        advisor.password_hash = hashed
        db.commit()
        return {"status": "success", "message": "Password updated successfully"}
    except HTTPException as he:

        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating advisor password: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update password: {str(e)}")


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
    client_email: Optional[str] = None
    client_name: Optional[str] = None

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
        user = db.query(User).filter(User.id == new_appt.user_id).first()
        client_email = user.email if user else None
        client_name = user.name if user else None
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
            joined=new_appt.joined,
            client_email=client_email,
            client_name=client_name
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
        appts = db.query(AdvisorAppointment, User.email, User.name).outerjoin(
            User, AdvisorAppointment.user_id == User.id
        ).filter(AdvisorAppointment.user_id == user_id).order_by(AdvisorAppointment.booked_at.desc()).all()
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
                joined=a.joined,
                client_email=email,
                client_name=name
            ) for a, email, name in appts
        ]
    except Exception as e:
        logger.error(f"Error fetching user appointments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch user appointments: {str(e)}")

@router.get("/appointments/advisor/{advisor_id}", response_model=List[AppointmentResponse])
async def get_advisor_appointments(advisor_id: str, db: Session = Depends(get_db)):
    try:
        appts = db.query(AdvisorAppointment, User.email, User.name).outerjoin(
            User, AdvisorAppointment.user_id == User.id
        ).filter(AdvisorAppointment.advisor_id == advisor_id).order_by(AdvisorAppointment.booked_at.desc()).all()
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
                joined=a.joined,
                client_email=email,
                client_name=name
            ) for a, email, name in appts
        ]
    except Exception as e:
        logger.error(f"Error fetching advisor appointments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch advisor appointments: {str(e)}")

@router.get("/appointments/all", response_model=List[AppointmentResponse])
async def get_all_appointments(db: Session = Depends(get_db)):
    try:
        appts = db.query(AdvisorAppointment, User.email, User.name).outerjoin(
            User, AdvisorAppointment.user_id == User.id
        ).order_by(AdvisorAppointment.booked_at.desc()).all()
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
                joined=a.joined,
                client_email=email,
                client_name=name
            ) for a, email, name in appts
        ]
    except Exception as e:
        logger.error(f"Error fetching all appointments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch all appointments: {str(e)}")

def update_advisor_rating_stats(advisor_id: str, db: Session):
    """
    Recalculates the advisor's average rating and review counts from completed appointments
    and updates the advisor's record.
    """
    try:
        ratings = db.query(AdvisorAppointment.rating).filter(
            AdvisorAppointment.advisor_id == advisor_id,
            AdvisorAppointment.completed == True,
            AdvisorAppointment.rating.isnot(None)
        ).all()
        
        advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == advisor_id).first()
        if advisor:
            if ratings:
                rating_values = [r[0] for r in ratings]
                advisor.rating = round(sum(rating_values) / len(rating_values), 1)
                advisor.reviews_count = len(rating_values)
            else:
                advisor.rating = 0.0
                advisor.reviews_count = 0
            db.commit()
            db.refresh(advisor)
            logger.info(f"Updated advisor {advisor_id} stats: rating={advisor.rating}, reviews={advisor.reviews_count}")
    except Exception as e:
        logger.error(f"Error updating advisor {advisor_id} stats: {e}", exc_info=True)

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
        
        # Trigger recalculation of advisor stats
        update_advisor_rating_stats(appt.advisor_id, db)
        
        user = db.query(User).filter(User.id == appt.user_id).first()
        client_email = user.email if user else None
        client_name = user.name if user else None
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
            joined=appt.joined,
            client_email=client_email,
            client_name=client_name
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
        user = db.query(User).filter(User.id == appt.user_id).first()
        client_email = user.email if user else None
        client_name = user.name if user else None
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
            joined=appt.joined,
            client_email=client_email,
            client_name=client_name
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
        user = db.query(User).filter(User.id == appt.user_id).first()
        client_email = user.email if user else None
        client_name = user.name if user else None
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
            joined=appt.joined,
            client_email=client_email,
            client_name=client_name
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error rescheduling appointment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reschedule appointment: {str(e)}")
