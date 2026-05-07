"""Tests for the persona profile schema used in response personalization."""

from src.utils.persona_profiles import (
    DEFAULT_PERSONA_ID,
    DEFAULT_PERSONA_PROFILES,
    PersonaProfile,
    get_persona_profile,
    list_persona_profiles,
)


def test_default_persona_profile_exists():
    """The default profile should always be available for fallback behavior."""

    profile = get_persona_profile()

    assert isinstance(profile, PersonaProfile)
    assert profile.profile_id == DEFAULT_PERSONA_ID
    assert profile.style.tone == "supportive"
    assert profile.style.empathy_level == 5


def test_named_persona_profile_can_be_loaded():
    """Named persona profiles should be retrievable by ID."""

    profile = get_persona_profile("practical_coach")

    assert profile.profile_id == "practical_coach"
    assert profile.style.directness == 4
    assert "action-oriented" in profile.tags


def test_unknown_persona_profile_falls_back_to_default():
    """Unknown profile IDs should fall back to the safe default persona."""

    profile = get_persona_profile("does_not_exist")

    assert profile.profile_id == DEFAULT_PERSONA_ID


def test_persona_registry_is_non_empty():
    """The built-in registry should contain the starter personas."""

    profiles = list_persona_profiles()

    assert len(profiles) == len(DEFAULT_PERSONA_PROFILES)
    assert {profile.profile_id for profile in profiles} == set(DEFAULT_PERSONA_PROFILES)
