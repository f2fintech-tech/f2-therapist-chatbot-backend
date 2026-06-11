"""
Security-focused middleware for request hardening.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque
from urllib.parse import urlparse


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _normalize_origin(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None

    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None

    return f"{parsed.scheme}://{parsed.netloc}"


class SecurityHeadersMiddleware:
    """Attach baseline security headers to every response."""

    def __init__(self, app, *, production: bool = False) -> None:
        self.app = app
        self.production = production

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                
                def set_header(k, v):
                    k_bytes = k.lower().encode()
                    if not any(h[0] == k_bytes for h in headers):
                        headers.append((k_bytes, v.encode()))

                set_header("X-Content-Type-Options", "nosniff")
                set_header("X-Frame-Options", "DENY")
                set_header("Referrer-Policy", "strict-origin-when-cross-origin")
                set_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
                set_header("X-Permitted-Cross-Domain-Policies", "none")
                set_header("Cache-Control", "no-store")

                if self.production:
                    set_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RequestSizeLimitMiddleware:
    """Reject requests that exceed the configured body size."""

    def __init__(self, app, *, max_body_bytes: int = 1_048_576, exempt_paths: set[str] | None = None) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.exempt_paths = exempt_paths or set()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        if not path.startswith("/api") or path in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")

        if content_length is not None:
            try:
                size = int(content_length.decode())
                if size > self.max_body_bytes:
                    await send({
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [(b"content-type", b"application/json")]
                    })
                    await send({
                        "type": "http.response.body",
                        "body": b'{"detail": "Request body too large"}',
                        "more_body": False
                    })
                    return
            except ValueError:
                await send({
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [(b"content-type", b"application/json")]
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"detail": "Invalid Content-Length header"}',
                    "more_body": False
                })
                return

        await self.app(scope, receive, send)


class RateLimitMiddleware:
    """Lightweight per-IP request rate limiting."""

    _request_history = defaultdict(deque)
    _lock = threading.Lock()

    def __init__(self, app, *, requests_per_minute: int = 200, window_seconds: int = 60, exempt_paths: set[str] | None = None) -> None:
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.exempt_paths = exempt_paths or set()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        method = scope["method"]
        if not path.startswith("/api") or path in self.exempt_paths or method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Extract client IP
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        headers = dict(scope.get("headers", []))
        forwarded_for = headers.get(b"x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.decode().split(",")[0].strip()

        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            bucket = self._request_history[client_ip]
            while bucket and bucket[0] < window_start:
                bucket.popleft()

            if len(bucket) >= self.requests_per_minute:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
                await send({
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", str(retry_after).encode())
                    ]
                })
                body = f'{{"detail": "Rate limit exceeded", "retry_after_seconds": {retry_after}}}'.encode()
                await send({
                    "type": "http.response.body",
                    "body": body,
                    "more_body": False
                })
                return

            bucket.append(now)

        await self.app(scope, receive, send)


class CSRFMiddleware:
    """Protect browser-originated unsafe requests with origin checks."""

    def __init__(self, app, *, enabled: bool = True, trusted_origins: list[str] | None = None, strict: bool = False) -> None:
        self.app = app
        self.enabled = enabled
        self.trusted_origins = {origin.rstrip("/") for origin in (trusted_origins or []) if origin.strip()}
        self.strict = strict

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]
        if not self.enabled or method in SAFE_METHODS or not path.startswith("/api"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        if b"authorization" in headers or b"x-api-key" in headers:
            await self.app(scope, receive, send)
            return

        cookie = headers.get(b"cookie")
        has_browser_cookies = bool(cookie)
        if not has_browser_cookies and not self.strict:
            await self.app(scope, receive, send)
            return

        origin = headers.get(b"origin", headers.get(b"referer"))
        normalized_origin = _normalize_origin(origin.decode() if origin else "")

        if not normalized_origin:
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")]
            })
            await send({
                "type": "http.response.body",
                "body": b'{"detail": "CSRF validation failed: missing origin"}',
                "more_body": False
            })
            return

        if self.trusted_origins and normalized_origin not in self.trusted_origins:
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")]
            })
            await send({
                "type": "http.response.body",
                "body": b'{"detail": "CSRF validation failed: untrusted origin"}',
                "more_body": False
            })
            return

        await self.app(scope, receive, send)
