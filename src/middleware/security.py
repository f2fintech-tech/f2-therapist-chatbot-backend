"""
Security-focused middleware for request hardening.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def _normalize_origin(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None

    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None

    return f"{parsed.scheme}://{parsed.netloc}"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers to every response."""

    def __init__(self, app, *, production: bool = False) -> None:
        super().__init__(app)
        self.production = production

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        response.headers.setdefault("Cache-Control", "no-store")

        if self.production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests that exceed the configured body size."""

    def __init__(self, app, *, max_body_bytes: int = 1_048_576, exempt_paths: set[str] | None = None) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes
        self.exempt_paths = exempt_paths or set()

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api") or request.url.path in self.exempt_paths:
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length is None:
            return await call_next(request)

        try:
            size = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header"},
            )

        if size > self.max_body_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": "Request body too large",
                    "max_bytes": self.max_body_bytes,
                },
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Lightweight per-IP request rate limiting."""

    _request_history: dict[str, Deque[float]] = defaultdict(deque)
    _lock = threading.Lock()

    def __init__(self, app, *, requests_per_minute: int = 200, window_seconds: int = 60, exempt_paths: set[str] | None = None) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.exempt_paths = exempt_paths or set()

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api") or request.url.path in self.exempt_paths:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        client_ip = _client_ip(request)
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            bucket = self._request_history[client_ip]
            while bucket and bucket[0] < window_start:
                bucket.popleft()

            if len(bucket) >= self.requests_per_minute:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "detail": "Rate limit exceeded",
                        "retry_after_seconds": retry_after,
                    },
                )

            bucket.append(now)

        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Protect browser-originated unsafe requests with origin checks."""

    def __init__(self, app, *, enabled: bool = True, trusted_origins: list[str] | None = None, strict: bool = False) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.trusted_origins = {origin.rstrip("/") for origin in (trusted_origins or []) if origin.strip()}
        self.strict = strict

    async def dispatch(self, request: Request, call_next):
        if not self.enabled or request.method in SAFE_METHODS or not request.url.path.startswith("/api"):
            return await call_next(request)

        if request.headers.get("authorization") or request.headers.get("x-api-key"):
            return await call_next(request)

        has_browser_cookies = bool(request.cookies)
        if not has_browser_cookies and not self.strict:
            return await call_next(request)

        origin = request.headers.get("origin") or request.headers.get("referer")
        normalized_origin = _normalize_origin(origin or "")

        if not normalized_origin:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed: missing origin"},
            )

        if self.trusted_origins and normalized_origin not in self.trusted_origins:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed: untrusted origin"},
            )

        return await call_next(request)