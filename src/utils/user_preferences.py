"""User preference schema and defaults for future response personalization.

This module only defines the data model and helper methods. Later steps can
load these preferences at runtime and combine them with a persona profile to
shape the final chat prompt.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional
import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


ResponseLengthType = Literal["short", "medium", "long"]
DetailLevelType = Literal["low", "medium", "high"]
ActionPreferenceType = Literal["reflect_first", "balanced", "action_first"]
QuestionStyleType = Literal["few", "normal", "many"]


class UserPreferenceProfile(BaseModel):
    """Saved preference settings for a single user."""

    user_id: str = Field(..., min_length=1, max_length=36)
    preferred_tone: Optional[str] = Field(default=None, max_length=50)
    response_length: ResponseLengthType = Field(default="medium")
    detail_level: DetailLevelType = Field(default="medium")
    action_preference: ActionPreferenceType = Field(default="balanced")
    question_style: QuestionStyleType = Field(default="normal")
    prefers_emotional_validation: bool = Field(default=True)
    prefers_practical_steps: bool = Field(default=True)
    prefers_follow_up_questions: bool = Field(default=True)
    avoids_topics: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("user_id", mode="before")
    def _strip_user_id(cls, value):
        """Keep stored user IDs normalized so lookups stay consistent."""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("preferred_tone", mode="before")
    def _strip_preferred_tone(cls, value):
        """Normalize free-text fields that will be injected into prompts later."""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("avoids_topics", mode="before")
    def _clean_avoids_topics(cls, value):
        """Remove blank entries and normalize topic names for easier matching."""
        if not isinstance(value, list):
            return []
        cleaned: List[str] = []
        for item in value:
            if isinstance(item, str):
                normalized = item.strip().lower()
                if normalized:
                    cleaned.append(normalized)
        return cleaned


# Keep a compact default registry so future steps can build without a DB.
DEFAULT_USER_PREFERENCES: Dict[str, UserPreferenceProfile] = {}


DEFAULT_USER_PREFERENCE = UserPreferenceProfile(
    user_id="default",
    preferred_tone="supportive",
    response_length="medium",
    detail_level="medium",
    action_preference="balanced",
    question_style="normal",
    prefers_emotional_validation=True,
    prefers_practical_steps=True,
    prefers_follow_up_questions=True,
    avoids_topics=[],
    notes="Safe default for users who have not set preferences yet.",
)


def get_user_preferences(user_id: Optional[str] = None) -> UserPreferenceProfile:
    """Return saved user preferences or a safe default if none exist."""

    if not user_id:
        return DEFAULT_USER_PREFERENCE

    normalized_user_id = user_id.strip().lower()
    return DEFAULT_USER_PREFERENCES.get(normalized_user_id, DEFAULT_USER_PREFERENCE)


def has_user_preferences(user_id: Optional[str] = None) -> bool:
    """Return True when we have stored preferences for the given user."""

    if not user_id:
        return False

    return user_id.strip().lower() in DEFAULT_USER_PREFERENCES


def save_user_preferences(profile: UserPreferenceProfile) -> UserPreferenceProfile:
    """Store preferences in memory for now so later steps can replace this with persistence.

    Step 2 stops at a data-layer abstraction: the function returns the saved
    profile and keeps the registry updated, but it does not introduce a database
    or API endpoint yet.
    """

    DEFAULT_USER_PREFERENCES[profile.user_id] = profile
    _save_persisted_preferences()
    return profile


def merge_user_preferences(
    base_profile: UserPreferenceProfile,
    updates: Dict[str, object],
) -> UserPreferenceProfile:
    """Create a new preference profile by applying partial updates.

    This keeps step 2 focused on structure and safe transformations without
    coupling the module to any chat prompt logic.
    """

    data = base_profile.model_dump()
    data.update(updates)
    data["user_id"] = base_profile.user_id
    merged = UserPreferenceProfile(**data)
    save_user_preferences(merged)
    return merged


# ------------------------------
# File-backed persistence helpers
# ------------------------------

_PREF_STORE_DIR = Path.cwd() / "src" / "data" / "personalization"
_PREF_STORE_PATH = _PREF_STORE_DIR / "preferences.json"


def _ensure_store_dir() -> None:
    try:
        _PREF_STORE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return


def _load_persisted_preferences() -> None:
    if not _PREF_STORE_PATH.exists():
        return
    try:
        data = json.loads(_PREF_STORE_PATH.read_text(encoding="utf-8"))
        for uid, payload in data.items():
            try:
                prof = UserPreferenceProfile(**payload)
                DEFAULT_USER_PREFERENCES[uid] = prof
            except Exception:
                continue
    except Exception:
        return


def _save_persisted_preferences() -> None:
    _ensure_store_dir()
    serializable = {uid: prof.model_dump() for uid, prof in DEFAULT_USER_PREFERENCES.items()}
    try:
        _PREF_STORE_PATH.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    except Exception:
        return


def delete_user_preferences(user_id: str) -> None:
    uid = user_id.strip().lower()
    if uid in DEFAULT_USER_PREFERENCES:
        DEFAULT_USER_PREFERENCES.pop(uid)
        _save_persisted_preferences()


# Load persisted preferences at import time (best-effort)
_load_persisted_preferences()
