"""
Authentication helper for optional API token protection.
"""

from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status 


def _expected_api_key() -> str | None:
    # The app only requires auth when the token is configured; local dev can run without it.
    value = os.getenv("API_ACCESS_TOKEN", "").strip()
    return value or None


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None

    return token.strip()


def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Validate the configured API token when one is present."""

    expected = _expected_api_key()
    if not expected:
        return None

    # Support both header styles so browser clients and service clients can share the same endpoint.
    provided = x_api_key or _extract_bearer_token(authorization)
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return None