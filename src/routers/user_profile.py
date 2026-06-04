"""
User Profile router — manages consolidated profile retrieval and tracking actions in JSON format.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Dict, Any, List

from src.models import get_db, User, UserConsolidatedProfile
from src.utils.api_security import require_api_key

router = APIRouter(prefix="/profile", tags=["User Profile"], dependencies=[Depends(require_api_key)])


# ==================== Schemas ====================

class TrackEducationRequest(BaseModel):
    content_type: Literal["video", "article"]
    content_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)


class TrackCalculatorRequest(BaseModel):
    inputs: Dict[str, Any]
    results: Dict[str, Any]


class TrackInteractionRequest(BaseModel):
    event: str = Field(..., min_length=1, max_length=100)
    details: Dict[str, Any] | None = None


# ==================== Helper Functions ====================

def get_or_create_consolidated_profile(db: Session, user_id: str) -> UserConsolidatedProfile:
    """Get the user's consolidated profile, or create it with a default JSON schema if not found."""
    profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == user_id).first()
    
    if not profile:
        profile = UserConsolidatedProfile(
            user_id=user_id,
            data={
                "profile_info": {},
                "financial_education": {
                    "videos_seen": [],
                    "articles_seen": []
                },
                "loan_calculator": {
                    "calculations_performed": []
                },
                "tests_attempted": [],
                "chatbot_interactions": []
            }
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        
    return profile


def sync_user_profile_fields(db: Session, user: User, profile: UserConsolidatedProfile):
    """Sync the fields stored on the User model into the consolidated JSON data."""
    data = dict(profile.data or {})
    
    if "profile_info" not in data:
        data["profile_info"] = {}
        
    data["profile_info"].update({
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "location": user.location,
        "occupation": user.occupation,
        "bio": user.bio,
        "financial_goal": user.financial_goal,
        "financial_stress": user.financial_stress,
        "risk_tolerance": user.risk_tolerance,
        "monthly_income": user.monthly_income,
        "therapy_style": user.therapy_style,
        "wellness_score": user.wellness_score,
        "wellness_tier": user.wellness_tier,
        "momentum_score": user.momentum_score,
    })
    
    profile.data = data
    flag_modified(profile, "data")
    db.commit()
    db.refresh(profile)


# ==================== Endpoints ====================

@router.get("/consolidated/{user_id}", response_model=Dict[str, Any])
def get_consolidated_profile(user_id: str, db: Session = Depends(get_db)):
    """Retrieve the entire consolidated user profile, syncing existing fields from the User table first."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    profile = get_or_create_consolidated_profile(db, user_id)
    sync_user_profile_fields(db, user, profile)
    return profile.data


@router.post("/track/education/{user_id}", status_code=status.HTTP_200_OK)
def track_education(user_id: str, payload: TrackEducationRequest, db: Session = Depends(get_db)):
    """Record a video or article seen on the financial education page."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    profile = get_or_create_consolidated_profile(db, user_id)
    data = dict(profile.data or {})
    
    # Ensure nested dictionary structure exists
    if "financial_education" not in data:
        data["financial_education"] = {}
    if "videos_seen" not in data["financial_education"]:
        data["financial_education"]["videos_seen"] = []
    if "articles_seen" not in data["financial_education"]:
        data["financial_education"]["articles_seen"] = []
        
    now_str = datetime.utcnow().isoformat()
    
    if payload.content_type == "video":
        data["financial_education"]["videos_seen"].append({
            "video_id": payload.content_id,
            "title": payload.title,
            "watched_at": now_str
        })
    else:
        data["financial_education"]["articles_seen"].append({
            "article_id": payload.content_id,
            "title": payload.title,
            "read_at": now_str
        })
        
    profile.data = data
    flag_modified(profile, "data")
    db.commit()
    return {"status": "success", "message": f"Tracked {payload.content_type} view"}


@router.post("/track/calculator/{user_id}", status_code=status.HTTP_200_OK)
def track_calculator(user_id: str, payload: TrackCalculatorRequest, db: Session = Depends(get_db)):
    """Record loan calculator usage."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    profile = get_or_create_consolidated_profile(db, user_id)
    data = dict(profile.data or {})
    
    # Ensure nested dictionary structure exists
    if "loan_calculator" not in data:
        data["loan_calculator"] = {}
    if "calculations_performed" not in data["loan_calculator"]:
        data["loan_calculator"]["calculations_performed"] = []
        
    data["loan_calculator"]["calculations_performed"].append({
        "timestamp": datetime.utcnow().isoformat(),
        "inputs": payload.inputs,
        "results": payload.results
    })
    
    profile.data = data
    flag_modified(profile, "data")
    db.commit()
    return {"status": "success", "message": "Tracked loan calculation"}


@router.post("/track/interaction/{user_id}", status_code=status.HTTP_200_OK)
def track_interaction(user_id: str, payload: TrackInteractionRequest, db: Session = Depends(get_db)):
    """Record a chatbot page event or user action."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    profile = get_or_create_consolidated_profile(db, user_id)
    data = dict(profile.data or {})
    
    # Ensure list structure exists
    if "chatbot_interactions" not in data:
        data["chatbot_interactions"] = []
        
    data["chatbot_interactions"].append({
        "event": payload.event,
        "timestamp": datetime.utcnow().isoformat(),
        "details": payload.details or {}
    })
    
    profile.data = data
    flag_modified(profile, "data")
    db.commit()
    return {"status": "success", "message": f"Tracked interaction: {payload.event}"}
