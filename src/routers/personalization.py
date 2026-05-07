from fastapi import APIRouter, HTTPException
from typing import List

from src.utils import persona_profiles, user_preferences
from src.utils.persona_profiles import PersonaProfile
from src.utils.user_preferences import UserPreferenceProfile

router = APIRouter(tags=["personalization"])

# Persona endpoints
@router.get("/personas", response_model=List[PersonaProfile])
async def list_personas():
    return persona_profiles.list_persona_profiles()

@router.get("/personas/{profile_id}", response_model=PersonaProfile)
async def get_persona(profile_id: str):
    prof = persona_profiles.get_persona_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Persona not found")
    return prof

@router.post("/personas", response_model=PersonaProfile)
async def create_persona(profile: PersonaProfile):
    if profile.profile_id in [p.profile_id for p in persona_profiles.list_persona_profiles()]:
        raise HTTPException(status_code=409, detail="Persona with that id already exists")
    return persona_profiles.create_persona_profile(profile)

@router.put("/personas/{profile_id}", response_model=PersonaProfile)
async def update_persona(profile_id: str, updates: dict):
    try:
        return persona_profiles.update_persona_profile(profile_id, updates)
    except KeyError:
        raise HTTPException(status_code=404, detail="Persona not found")

@router.delete("/personas/{profile_id}")
async def delete_persona(profile_id: str):
    persona_profiles.delete_persona_profile(profile_id)
    return {"ok": True}

# User preference endpoints
@router.get("/preferences/{user_id}", response_model=UserPreferenceProfile)
async def get_preferences(user_id: str):
    return user_preferences.get_user_preferences(user_id)

@router.post("/preferences", response_model=UserPreferenceProfile)
async def create_preferences(profile: UserPreferenceProfile):
    existing = user_preferences.has_user_preferences(profile.user_id)
    if existing:
        raise HTTPException(status_code=409, detail="Preferences for this user already exist")
    user_preferences.save_user_preferences(profile)
    return profile

@router.put("/preferences/{user_id}", response_model=UserPreferenceProfile)
async def update_preferences(user_id: str, updates: dict):
    current = user_preferences.get_user_preferences(user_id)
    if current.user_id == "default" and not user_preferences.has_user_preferences(user_id):
        # No existing explicit preferences; create one from defaults
        base = user_preferences.DEFAULT_USER_PREFERENCE
        base_data = base.model_dump()
        base_data["user_id"] = user_id.strip().lower()
        merged = user_preferences.UserPreferenceProfile(**{**base_data, **updates})
        user_preferences.save_user_preferences(merged)
        return merged

    merged = user_preferences.merge_user_preferences(current, updates)
    return merged

@router.delete("/preferences/{user_id}")
async def delete_preferences(user_id: str):
    user_preferences.delete_user_preferences(user_id)
    return {"ok": True}
