"""Persona profile schema and defaults for future response personalization.

Step 1 only defines the structure and ready-to-use defaults. It does not
change the chat prompt yet; later steps can import these profiles and inject
them into the response builder.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional
import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


ToneType = Literal["warm", "supportive", "calm", "direct", "encouraging", "professional"]
VerbosityType = Literal["short", "medium", "detailed"]
FormalityType = Literal["casual", "neutral", "formal"]
AdviceStyleType = Literal["reflective", "practical", "coaching", "balanced"]


class PersonaStyle(BaseModel):
    """Low-level response style settings used to shape the assistant voice."""

    tone: ToneType = Field(default="supportive", description="High-level emotional tone")
    empathy_level: int = Field(default=5, ge=1, le=5, description="How much emotional validation to show")
    directness: int = Field(default=3, ge=1, le=5, description="How direct and action-oriented the response should be")
    verbosity: VerbosityType = Field(default="medium", description="How long and detailed the response should be")
    formality: FormalityType = Field(default="neutral", description="How formal the wording should sound")
    advice_style: AdviceStyleType = Field(default="balanced", description="Whether the assistant should reflect, coach, or solve")


class PersonaProfile(BaseModel):
    """Named persona profile that can be selected for a given user or context."""

    profile_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=500)
    style: PersonaStyle = Field(default_factory=PersonaStyle)
    response_goals: List[str] = Field(default_factory=list)
    do_listen: bool = Field(default=True, description="Whether the persona should prioritize listening first")
    do_offer_steps: bool = Field(default=True, description="Whether the persona should offer concrete next steps")
    tags: List[str] = Field(default_factory=list)

    @field_validator("profile_id", "name", "description", mode="before")
    def _strip_text_fields(cls, value):
        """Trim whitespace so profile definitions stay consistent in JSON and code."""
        return value.strip() if isinstance(value, str) else value


# Keep a small starter registry so future steps can choose from known personas.
DEFAULT_PERSONA_PROFILES: Dict[str, PersonaProfile] = {
    "balanced_support": PersonaProfile(
        profile_id="balanced_support",
        name="Balanced Support",
        description="A calm and empathetic persona that listens first, then gives clear next steps.",
        style=PersonaStyle(
            tone="supportive",
            empathy_level=5,
            directness=3,
            verbosity="medium",
            formality="neutral",
            advice_style="balanced",
        ),
        response_goals=[
            "validate the user's feelings",
            "explain options in plain language",
            "offer one or two practical next steps",
        ],
        tags=["default", "empathetic", "balanced"],
    ),
    "practical_coach": PersonaProfile(
        profile_id="practical_coach",
        name="Practical Coach",
        description="A slightly more direct persona that still stays kind while focusing on action.",
        style=PersonaStyle(
            tone="encouraging",
            empathy_level=4,
            directness=4,
            verbosity="short",
            formality="neutral",
            advice_style="coaching",
        ),
        response_goals=[
            "reduce overwhelm quickly",
            "prioritize the most useful next action",
            "keep the answer concise and usable",
        ],
        tags=["action-oriented", "concise", "coaching"],
    ),
    "gentle_listener": PersonaProfile(
        profile_id="gentle_listener",
        name="Gentle Listener",
        description="A softer persona that emphasizes reflection, reassurance, and emotional safety.",
        style=PersonaStyle(
            tone="warm",
            empathy_level=5,
            directness=2,
            verbosity="detailed",
            formality="casual",
            advice_style="reflective",
        ),
        response_goals=[
            "reflect feelings before giving advice",
            "avoid sounding rushed or overly technical",
            "offer reassurance and a gentle next step",
        ],
        tags=["warm", "reflective", "support-first"],
    ),
}


DEFAULT_PERSONA_ID = "balanced_support"


def get_persona_profile(profile_id: Optional[str] = None) -> PersonaProfile:
    """Return a persona profile, falling back to the safe default if needed."""

    selected_id = (profile_id or DEFAULT_PERSONA_ID).strip()
    # Check persisted registry first (loaded into DEFAULT_PERSONA_PROFILES at import)
    return DEFAULT_PERSONA_PROFILES.get(selected_id, DEFAULT_PERSONA_PROFILES[DEFAULT_PERSONA_ID])


def has_persona_profile(profile_id: Optional[str] = None) -> bool:
    """Return True when the requested profile exists in the built-in registry."""

    if not profile_id:
        return False

    return profile_id.strip() in DEFAULT_PERSONA_PROFILES


def list_persona_profiles() -> List[PersonaProfile]:
    """Return all built-in personas in a stable order for future UI selection."""

    return list(DEFAULT_PERSONA_PROFILES.values())


# ------------------------------
# File-backed persistence helpers
# ------------------------------

_PERSONA_STORE_DIR = Path.cwd() / "src" / "data" / "personalization"
_PERSONA_STORE_PATH = _PERSONA_STORE_DIR / "personas.json"


def _ensure_store_dir() -> None:
    try:
        _PERSONA_STORE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Best-effort: if the environment disallows writes, keep working in-memory
        return


def _load_persisted_personas() -> None:
    if not _PERSONA_STORE_PATH.exists():
        return

    try:
        data = json.loads(_PERSONA_STORE_PATH.read_text(encoding="utf-8"))
        for pid, payload in data.items():
            try:
                prof = PersonaProfile(**payload)
                DEFAULT_PERSONA_PROFILES[pid] = prof
            except Exception:
                # Skip invalid entries rather than failing startup
                continue
    except Exception:
        return


def _save_persisted_personas() -> None:
    _ensure_store_dir()
    serializable = {pid: prof.model_dump() for pid, prof in DEFAULT_PERSONA_PROFILES.items()}
    try:
        _PERSONA_STORE_PATH.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    except Exception:
        # Best-effort persistence; swallow write errors
        return


def create_persona_profile(profile: PersonaProfile) -> PersonaProfile:
    pid = profile.profile_id.strip()
    DEFAULT_PERSONA_PROFILES[pid] = profile
    _save_persisted_personas()
    return profile


def update_persona_profile(profile_id: str, updates: Dict) -> PersonaProfile:
    pid = profile_id.strip()
    if pid not in DEFAULT_PERSONA_PROFILES:
        raise KeyError(pid)
    data = DEFAULT_PERSONA_PROFILES[pid].model_dump()
    data.update(updates)
    data["profile_id"] = pid
    updated = PersonaProfile(**data)
    DEFAULT_PERSONA_PROFILES[pid] = updated
    _save_persisted_personas()
    return updated


def delete_persona_profile(profile_id: str) -> None:
    pid = profile_id.strip()
    if pid in DEFAULT_PERSONA_PROFILES:
        # Do not delete the built-in default entirely; if deleting default, reset to safe default
        if pid == DEFAULT_PERSONA_ID:
            DEFAULT_PERSONA_PROFILES[pid] = DEFAULT_PERSONA_PROFILES[DEFAULT_PERSONA_ID]
        else:
            DEFAULT_PERSONA_PROFILES.pop(pid)
        _save_persisted_personas()


# Load persisted personas at import time (best-effort)
_load_persisted_personas()
