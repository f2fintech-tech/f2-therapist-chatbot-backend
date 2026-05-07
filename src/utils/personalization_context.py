"""Combined persona + preference resolution for chat prompt personalization.

Step 4 makes fallback behavior explicit. When no custom persona or user
preferences are stored yet, the chat flow can still use safe defaults and tell
the prompt builder exactly what happened.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.utils.persona_profiles import PersonaProfile, get_persona_profile, has_persona_profile
from src.utils.user_preferences import UserPreferenceProfile, get_user_preferences, has_user_preferences


@dataclass(frozen=True)
class PersonalizationContext:
    """Resolved personalization inputs plus fallback metadata."""

    user_id: str
    persona_profile: PersonaProfile
    user_preferences: UserPreferenceProfile
    used_default_persona: bool
    used_default_preferences: bool

    @property
    def used_defaults(self) -> bool:
        """True when any personalization input fell back to the safe default."""

        return self.used_default_persona or self.used_default_preferences


def resolve_personalization_context(user_id: str, persona_id: str | None = None) -> PersonalizationContext:
    """Resolve the best available persona and preference settings for a user.

    This keeps the chat route simple: it asks for one resolved context and gets
    both the active settings and a clear signal when defaults were used.
    """

    persona_profile = get_persona_profile(persona_id)
    user_preferences = get_user_preferences(user_id)

    normalized_user_id = user_id.strip().lower()
    used_default_persona = not persona_id or not has_persona_profile(persona_id)
    used_default_preferences = not has_user_preferences(normalized_user_id)

    return PersonalizationContext(
        user_id=normalized_user_id,
        persona_profile=persona_profile,
        user_preferences=user_preferences,
        used_default_persona=used_default_persona,
        used_default_preferences=used_default_preferences,
    )


def build_personalization_fallback_guidance(context: PersonalizationContext) -> str:
    """Explain any fallback used so the prompt stays honest and consistent.

    The model should not assume custom settings exist when they do not. This
    block tells it to keep using the default supportive style until the user
    configures a profile.
    """

    if not context.used_defaults:
        return ""

    lines = ["Personalization fallback:"]

    if context.used_default_persona:
        lines.append("- No custom persona profile was provided, so use the default supportive persona.")

    if context.used_default_preferences:
        lines.append("- No saved user preferences were found, so use the default medium-length, balanced response style.")

    lines.append("- Keep the answer warm, practical, and safe even without custom settings.")
    return "\n".join(lines)
