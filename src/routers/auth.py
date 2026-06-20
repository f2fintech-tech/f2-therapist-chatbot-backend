"""
Authentication router — signup, login, token refresh, hearts management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta
from typing import List, Dict, Any
import bcrypt as _bcrypt
from jose import jwt
from src.models import get_db, User, Conversation, Advisor, UserCreditReport, UserConsolidatedProfile, UserLoanCalculatorActivity, TestResult, UserSessionReport, ReferralCode
from src.utils.api_security import require_api_key
import os
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"], dependencies=[Depends(require_api_key)])

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-secret-change-in-prod")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))
INITIAL_HEARTS = 50
HEARTS_PER_MESSAGE = 10



class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str = Field(..., min_length=1, max_length=100)
    guest_user_id: str | None = None
    invite_token: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    name: str
    hearts: int
    is_guest: bool


class UserProfileResponse(BaseModel):
    user_id: str
    email: str | None = None
    name: str
    phone: str | None = None
    location: str | None = None
    occupation: str | None = None
    bio: str | None = None
    financial_goal: str | None = None
    financial_stress: str | None = None
    risk_tolerance: str | None = None
    monthly_income: str | None = None
    therapy_style: str | None = None
    hearts: int
    is_guest: bool
    goals: List[Dict[str, Any]] | None = None


class UpdateUserProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    location: str | None = Field(default=None, max_length=255)
    occupation: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=2000)
    financial_goal: str | None = Field(default=None, max_length=255)
    financial_stress: str | None = Field(default=None, max_length=255)
    risk_tolerance: str | None = Field(default=None, max_length=255)
    monthly_income: str | None = Field(default=None, max_length=255)
    therapy_style: str | None = Field(default=None, max_length=255)


class HeartsResponse(BaseModel):
    user_id: str
    hearts: int
    can_chat: bool


class DeductHeartsRequest(BaseModel):
    user_id: str


class GuestInitRequest(BaseModel):
    user_id: str


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: str, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


@router.post("/guest", response_model=HeartsResponse)
def init_guest(payload: GuestInitRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        user = User(
            id=payload.user_id,
            email=None,
            name="Guest",
            hashed_password=None,
            hearts=INITIAL_HEARTS,
            is_guest="true",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Guest user created: %s with %d hearts", payload.user_id, INITIAL_HEARTS)

    return HeartsResponse(
        user_id=user.id,
        hearts=user.hearts,
        can_chat=user.hearts >= HEARTS_PER_MESSAGE,
    )


@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    referred_by_advisor_id = None
    if payload.invite_token:
        try:
            ref = db.query(ReferralCode).filter(ReferralCode.code == payload.invite_token, ReferralCode.status == "pending").first()
            if not ref or ref.expires_at < datetime.utcnow():
                raise HTTPException(status_code=400, detail="Invalid or expired referral code")
            referred_by_advisor_id = ref.advisor_id
            ref.status = "used"
            ref.used_at = datetime.utcnow()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error querying referral code: {e}")
            raise HTTPException(status_code=400, detail="Referral code system is currently unavailable.")

    new_id = str(uuid.uuid4())
    user = User(
        id=new_id,
        email=payload.email,
        name=payload.name,
        hashed_password=hash_password(payload.password),
        hearts=INITIAL_HEARTS,
        is_guest="false"
    )
    db.add(user)
    db.flush()

    if payload.invite_token and referred_by_advisor_id:
        ref.status = "used"
        ref.used_at = datetime.utcnow()
        ref.referred_user_id = new_id

    db.commit()

    if payload.guest_user_id:
        guest = db.query(User).filter(User.id == payload.guest_user_id).first()
        if guest and guest.is_guest == "true":
            if guest.goals:
                updated_goals = []
                for g in guest.goals:
                    if isinstance(g, dict):
                        g_copy = dict(g)
                        g_copy["userId"] = new_id
                        updated_goals.append(g_copy)
                user.goals = updated_goals
            db.query(Conversation).filter(
                Conversation.user_id == payload.guest_user_id
            ).update({"user_id": new_id})
            
            db.query(UserCreditReport).filter(
                UserCreditReport.user_id == payload.guest_user_id
            ).update({"user_id": new_id})
            
            db.query(UserLoanCalculatorActivity).filter(
                UserLoanCalculatorActivity.user_id == payload.guest_user_id
            ).update({"user_id": new_id})
            
            db.query(TestResult).filter(
                TestResult.user_id == payload.guest_user_id
            ).update({"user_id": new_id})
            
            db.query(UserSessionReport).filter(
                UserSessionReport.user_id == payload.guest_user_id
            ).update({"user_id": new_id})
            
            # Migrate/merge consolidated profile
            guest_profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == payload.guest_user_id).first()
            if guest_profile:
                dest_profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == new_id).first()
                if not dest_profile:
                    guest_profile.user_id = new_id
                else:
                    if dest_profile.data is None:
                        dest_profile.data = {}
                    if guest_profile.data:
                        for k, v in guest_profile.data.items():
                            if k not in dest_profile.data:
                                dest_profile.data[k] = v
                        flag_modified(dest_profile, "data")
                    db.delete(guest_profile)
                    
            db.delete(guest)
            db.commit()
            logger.info("Merged guest %s into new user %s", payload.guest_user_id, new_id)

    db.refresh(user)
    token = create_token(user.id, user.email)
    return AuthResponse(
        token=token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        hearts=user.hearts,
        is_guest=False,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user.id, user.email)
    logger.info("User logged in: %s", user.email)
    return AuthResponse(
        token=token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        hearts=user.hearts,
        is_guest=False,
    )


@router.get("/hearts/{user_id}", response_model=HeartsResponse)
def get_hearts(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return HeartsResponse(
        user_id=user.id,
        hearts=user.hearts,
        can_chat=user.hearts >= HEARTS_PER_MESSAGE,
    )


@router.post("/hearts/deduct", response_model=HeartsResponse)
def deduct_hearts(payload: DeductHeartsRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.hearts < HEARTS_PER_MESSAGE:
        raise HTTPException(status_code=402, detail="Not enough hearts")
    user.hearts = max(0, user.hearts - HEARTS_PER_MESSAGE)
    db.commit()
    db.refresh(user)
    return HeartsResponse(
        user_id=user.id,
        hearts=user.hearts,
        can_chat=user.hearts >= HEARTS_PER_MESSAGE,
    )


@router.get("/profile/{user_id}", response_model=UserProfileResponse)
def get_profile(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfileResponse(
        user_id=user.id,
        email=user.email,
        name=user.name or "Guest",
        phone=user.phone,
        location=user.location,
        occupation=user.occupation,
        bio=user.bio,
        financial_goal=user.financial_goal,
        financial_stress=user.financial_stress,
        risk_tolerance=user.risk_tolerance,
        monthly_income=user.monthly_income,
        therapy_style=user.therapy_style,
        hearts=user.hearts,
        is_guest=user.is_guest == "true",
        goals=user.goals or [],
    )


@router.put("/profile/{user_id}", response_model=UserProfileResponse)
def update_profile(user_id: str, payload: UpdateUserProfileRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_email = payload.email.strip() if payload.email else None
    if new_email and new_email != user.email:
        existing_email = db.query(User).filter(User.email == new_email, User.id != user_id).first()
        if existing_email:
            raise HTTPException(status_code=409, detail="Email already registered")
        user.email = new_email

    user.name = payload.name.strip()
    user.phone = payload.phone.strip() if payload.phone else None
    user.location = payload.location.strip() if payload.location else None
    user.occupation = payload.occupation.strip() if payload.occupation else None
    user.bio = payload.bio.strip() if payload.bio else None
    user.financial_goal = payload.financial_goal.strip() if payload.financial_goal else None
    user.financial_stress = payload.financial_stress.strip() if payload.financial_stress else None
    user.risk_tolerance = payload.risk_tolerance.strip() if payload.risk_tolerance else None
    user.monthly_income = payload.monthly_income.strip() if payload.monthly_income else None
    user.therapy_style = payload.therapy_style.strip() if payload.therapy_style else None
    db.commit()
    db.refresh(user)

    return UserProfileResponse(
        user_id=user.id,
        email=user.email,
        name=user.name or "Guest",
        phone=user.phone,
        location=user.location,
        occupation=user.occupation,
        bio=user.bio,
        financial_goal=user.financial_goal,
        financial_stress=user.financial_stress,
        risk_tolerance=user.risk_tolerance,
        monthly_income=user.monthly_income,
        therapy_style=user.therapy_style,
        hearts=user.hearts,
        is_guest=user.is_guest == "true",
        goals=user.goals or [],
    )


@router.get("/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    registered_users = db.query(User).filter(User.is_guest == "false").count()
    guest_users = db.query(User).filter(User.is_guest == "true").count()
    total_conversations = db.query(Conversation).count()
    
    return {
        "total_users": total_users,
        "registered_users": registered_users,
        "guest_users": guest_users,
        "total_conversations": total_conversations
    }


@router.put("/profile/{user_id}/goals")
def update_user_goals(user_id: str, payload: List[Dict[str, Any]], db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.goals = payload
    flag_modified(user, "goals")
    db.commit()
    db.refresh(user)
    return {"status": "success", "goals": user.goals}


# ==================== Advisor Auth Endpoints ====================

class AdvisorSignupRequest(BaseModel):
    f2_fintech_id: str
    designation: str
    password: str = Field(..., min_length=6)
    confirm_password: str

class AdvisorLoginRequest(BaseModel):
    f2_fintech_id: str
    password: str

class AdvisorAuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    name: str
    hearts: int
    is_guest: bool
    is_advisor: bool = True

@router.post("/advisor/signup", response_model=AdvisorAuthResponse)
def advisor_signup(payload: AdvisorSignupRequest, db: Session = Depends(get_db)):
    f2_id = payload.f2_fintech_id.strip()
    designation = payload.designation.strip()
    
    # Verify employee exists in advisors table
    advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_id).first()
    if not advisor:
        raise HTTPException(
            status_code=404, 
            detail="Employer not found. Check your credentials again."
        )
        
    # Check designation matching case-insensitively
    if advisor.designation.lower().strip() != designation.lower().strip():
        raise HTTPException(
            status_code=404, 
            detail="Employer not found. Check your credentials again."
        )
        
    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Passwords do not match."
        )
        
    if advisor.password_hash:
        raise HTTPException(
            status_code=400,
            detail="Employer account already registered."
        )
        
    advisor.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(advisor)
    
    token = create_token(advisor.f2_fintech_id, f"{advisor.f2_fintech_id}@f2fintech.com")
    logger.info("Advisor registered: %s", advisor.f2_fintech_id)
    
    return AdvisorAuthResponse(
        token=token,
        user_id=advisor.f2_fintech_id,
        email=f"{advisor.f2_fintech_id}@f2fintech.com",
        name=advisor.name,
        hearts=99999,
        is_guest=False,
        is_advisor=True
    )

@router.post("/advisor/login", response_model=AdvisorAuthResponse)
def advisor_login(payload: AdvisorLoginRequest, db: Session = Depends(get_db)):
    f2_id = payload.f2_fintech_id.strip()
    
    advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == f2_id).first()
    if not advisor or not advisor.password_hash:
        raise HTTPException(
            status_code=401,
            detail="Invalid F2 Fintech ID or password."
        )
        
    if not verify_password(payload.password, advisor.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid F2 Fintech ID or password."
        )
        
    token = create_token(advisor.f2_fintech_id, f"{advisor.f2_fintech_id}@f2fintech.com")
    logger.info("Advisor logged in: %s", advisor.f2_fintech_id)
    
    return AdvisorAuthResponse(
        token=token,
        user_id=advisor.f2_fintech_id,
        email=f"{advisor.f2_fintech_id}@f2fintech.com",
        name=advisor.name,
        hearts=99999,
        is_guest=False,
        is_advisor=True
    )


class ChangePasswordRequest(BaseModel):
    user_id: str
    current_password: str
    new_password: str = Field(..., min_length=6)


@router.put("/change-password")
def change_password(payload: ChangePasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.hashed_password:
        raise HTTPException(status_code=400, detail="This account has no password set (guest account)")

    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    logger.info("Password changed for user: %s", user.id)
    return {"status": "success", "message": "Password changed successfully"}