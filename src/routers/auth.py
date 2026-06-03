"""
Authentication router — signup, login, token refresh, hearts management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta
import bcrypt as _bcrypt
from jose import jwt
from src.models import get_db, User, Conversation
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

    new_id = str(uuid.uuid4())
    user = User(
        id=new_id,
        email=payload.email,
        name=payload.name,
        hashed_password=hash_password(payload.password),
        hearts=INITIAL_HEARTS,
        is_guest="false",
    )
    db.add(user)
    db.commit()

    if payload.guest_user_id:
        guest = db.query(User).filter(User.id == payload.guest_user_id).first()
        if guest and guest.is_guest == "true":
            db.query(Conversation).filter(
                Conversation.user_id == payload.guest_user_id
            ).update({"user_id": new_id})
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