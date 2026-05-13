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