"""Tests for fallback behavior when no custom persona or preferences exist."""

from src.utils.personalization_context import (
    build_personalization_fallback_guidance,
    resolve_personalization_context,
)


def test_personalization_context_uses_default_settings_when_missing():
    """A new user should resolve to the safe default persona and preferences."""

    context = resolve_personalization_context("123e4567-e89b-12d3-a456-426614174000")

    assert context.used_default_persona is True
    assert context.used_default_preferences is True
    assert context.persona_profile.profile_id == "balanced_support"
    assert context.user_preferences.user_id == "default"


def test_personalization_fallback_guidance_is_explicit():
    """The fallback block should tell the model that default settings are in use."""

    context = resolve_personalization_context("123e4567-e89b-12d3-a456-426614174000")
    guidance = build_personalization_fallback_guidance(context)

    assert "Personalization fallback:" in guidance
    assert "default supportive persona" in guidance
    assert "default medium-length, balanced response style" in guidance
