"""Tests for the user preference schema used in response personalization."""

from src.utils.user_preferences import (
    DEFAULT_USER_PREFERENCE,
    UserPreferenceProfile,
    get_user_preferences,
    merge_user_preferences,
    save_user_preferences,
)


def test_default_user_preferences_are_returned_when_missing():
    """A missing user should fall back to the safe default profile."""

    profile = get_user_preferences()

    assert isinstance(profile, UserPreferenceProfile)
    assert profile.user_id == "default"
    assert profile.preferred_tone == "supportive"
    assert profile.response_length == "medium"


def test_user_preferences_are_normalized_and_saved():
    """Saved preferences should normalize user IDs and free-text values."""

    profile = UserPreferenceProfile(
        user_id="  123E4567-E89B-12D3-A456-426614174000  ",
        preferred_tone="  Warm  ",
        response_length="short",
        detail_level="low",
        action_preference="reflect_first",
        question_style="few",
        avoids_topics=["  debt  ", "", "  stress management "],
    )

    saved = save_user_preferences(profile)

    assert saved.user_id == "123e4567-e89b-12d3-a456-426614174000"
    assert saved.preferred_tone == "warm"
    assert saved.avoids_topics == ["debt", "stress management"]


def test_merge_user_preferences_preserves_user_identity():
    """Partial updates should keep the same user identity while changing settings."""

    base = DEFAULT_USER_PREFERENCE
    merged = merge_user_preferences(base, {"response_length": "long", "preferred_tone": "calm"})

    assert merged.user_id == base.user_id
    assert merged.response_length == "long"
    assert merged.preferred_tone == "calm"


def test_get_user_preferences_returns_saved_profile():
    """Once a profile is saved, lookups should return the stored version."""

    profile = UserPreferenceProfile(
        user_id="user-abc",
        preferred_tone="direct",
        response_length="short",
        detail_level="high",
        action_preference="action_first",
        question_style="many",
    )
    save_user_preferences(profile)

    loaded = get_user_preferences("USER-ABC")

    assert loaded.user_id == "user-abc"
    assert loaded.preferred_tone == "direct"
    assert loaded.response_length == "short"
