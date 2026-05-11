"""
Financial Therapist Chatbot Backend
FastAPI application with Google Gemini 3 flash preview API integration
"""

from fastapi import FastAPI, Request, HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import RedirectResponse
from dotenv import load_dotenv
import os
import logging
from urllib.parse import urlparse

# Import routers
from src.routers import health, chat, conversations
from src.routers import personalization
from src.models import init_db

# Import middleware
from src.middleware.logging import RequestLoggingMiddleware, SecurityLoggingMiddleware
from src.middleware.security import (
    CSRFMiddleware,
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _parse_hosts_from_origins(origins):
    """Extract host names from CORS origin URLs."""
    hosts = []
    for origin in origins:
        origin = origin.strip()
        if not origin:
            continue

        parsed = urlparse(origin)
        if parsed.hostname:
            hosts.append(parsed.hostname)

    return hosts


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect incoming HTTP requests to HTTPS in production."""

    async def dispatch(self, request: Request, call_next):
        if ENVIRONMENT == "production":
            forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            if forwarded_proto != "https":
                secure_url = request.url.replace(scheme="https")
                return RedirectResponse(str(secure_url), status_code=308)

        return await call_next(request)

# ==================== Rate Limiting Setup ====================
# ==================== FastAPI Initialization ====================
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "200"))
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(1_048_576)))
# Keep CSRF on by default so browser-originated requests are validated unless explicitly disabled.
CSRF_PROTECTION_ENABLED = os.getenv("CSRF_PROTECTION_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
CSRF_STRICT = os.getenv("CSRF_STRICT", "false").strip().lower() in {"1", "true", "yes", "on"}
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", os.getenv("ALLOWED_ORIGINS", "")).split(",")
    if origin.strip()
]

app = FastAPI(
    title="Financial Therapist Chatbot",
    description="AI-powered financial therapy chatbot backend with Google Gemini 3 Flash preview integration.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# ==================== Middleware Stack ====================
# Order matters: Security → Logging → CORS (outermost)

# Trusted host middleware prevents host header attacks in production.
# `testserver` is included so the TestClient can exercise the app without failing host checks.
DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS")

if ALLOWED_HOSTS:
    ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS.split(",") if host.strip()]
else:
    ALLOWED_HOSTS = DEFAULT_ALLOWED_HOSTS if ENVIRONMENT != "production" else _parse_hosts_from_origins(
        os.getenv("ALLOWED_ORIGINS", "").split(",")
    )

if ENVIRONMENT == "production" and not ALLOWED_HOSTS:
    logger.warning(
        "ALLOWED_HOSTS not set in production and no hosts could be derived from ALLOWED_ORIGINS. "
        "Using localhost-only fallback; set ALLOWED_HOSTS explicitly for deployment."
    )
    ALLOWED_HOSTS = DEFAULT_ALLOWED_HOSTS

logger.info(f"Allowed hosts: {ALLOWED_HOSTS}")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# Security middleware is applied before observability so rejected requests do not waste work.
app.add_middleware(SecurityHeadersMiddleware, production=ENVIRONMENT == "production")
app.add_middleware(CSRFMiddleware, enabled=CSRF_PROTECTION_ENABLED, trusted_origins=CSRF_TRUSTED_ORIGINS, strict=CSRF_STRICT)
app.add_middleware(RateLimitMiddleware, requests_per_minute=RATE_LIMIT_REQUESTS_PER_MINUTE, exempt_paths={"/health", "/docs", "/redoc", "/openapi.json"})
app.add_middleware(RequestSizeLimitMiddleware, max_body_bytes=MAX_REQUEST_BODY_BYTES, exempt_paths={"/health", "/docs", "/redoc", "/openapi.json"})
app.add_middleware(HTTPSRedirectMiddleware)

# Logging stays outermost so we still get a trace when one of the security layers rejects a request.
app.add_middleware(SecurityLoggingMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware (added last, processed first)
# Get allowed origins from environment variable.
# Local development defaults include common frontend ports.
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
).split(",")

# Codespaces frontend URLs are dynamic (https://<name>-5173.app.github.dev).
# Keep this permissive pattern for non-production only unless explicitly configured.
ALLOW_ORIGIN_REGEX = r"https://.*\.app\.github\.dev" if ENVIRONMENT != "production" else None

# For production, default to no origins (explicitly set required)
if ENVIRONMENT == "production":
    if os.getenv("ALLOWED_ORIGINS") is None:
        logger.warning("ALLOWED_ORIGINS not set in production. CORS disabled for safety.")
        ALLOWED_ORIGINS = []

logger.info(f"Environment: {ENVIRONMENT}")
logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")
logger.info(f"Rate limit: {RATE_LIMIT_REQUESTS_PER_MINUTE} requests/minute per IP")
logger.info(f"Max request body: {MAX_REQUEST_BODY_BYTES} bytes")
logger.info(f"CSRF protection enabled: {CSRF_PROTECTION_ENABLED}")

# Configure CORS with secure settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# ==================== Database Initialization ====================
init_db()

# ==================== Include Routers ====================
# Health check routes
app.include_router(health.router)

# Chat routes (v1 API) with rate limiting
app.include_router(chat.router, prefix="/api/v1")

# Conversation management routes (v1 API) with rate limiting
app.include_router(conversations.router, prefix="/api/v1")

# Personalization management endpoints (personas, preferences)
app.include_router(personalization.router, prefix="/api/v1")

# ==================== Root Routes ====================
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information.
    """
    return {
        "message": "Financial Therapist Chatbot API",
        "version": "1.0.0",
        "environment": ENVIRONMENT,
        "documentation": "/docs",
        "api_base": "/api/v1",
        "rate_limit": f"{RATE_LIMIT_REQUESTS_PER_MINUTE} requests per minute"
    }

# ==================== Startup/Shutdown Events ====================
@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("=" * 60)
    logger.info("Starting Financial Therapist Chatbot Backend")
    logger.info("=" * 60)
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Google Gemini API configured: {bool(os.getenv('GEMINI_API_KEY'))}")
    logger.info(f"Database configured: {bool(os.getenv('DATABASE_URL'))}")
    logger.info(f"Rate limiting: {RATE_LIMIT_REQUESTS_PER_MINUTE} requests per minute per IP")
    logger.info("Logging middleware: Enabled")
    logger.info("Security logging: Enabled")
    logger.info(f"Request size limit: {MAX_REQUEST_BODY_BYTES} bytes")
    logger.info(f"CSRF protection: {CSRF_PROTECTION_ENABLED}")
    logger.info("API Documentation available at: /docs")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("=" * 60)
    logger.info("Shutting down Financial Therapist Chatbot Backend")
    logger.info("=" * 60)

# ==================== Global Error Handler ====================
def _error_payload(error: str, detail, path: str) -> dict:
    # Use one small helper so all error responses share the same JSON shape.
    return {
        "error": error,
        "detail": detail,
        "path": path,
    }


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """Return structured JSON for expected HTTP errors."""
    logger.warning(
        "HTTP error on %s %s: %s",
        request.method,
        request.url.path,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            error="Request failed",
            detail=exc.detail,
            path=request.url.path,
        ),
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return structured JSON for request body and parameter validation errors."""
    logger.warning(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            error="Validation failed",
            detail=exc.errors(),
            path=request.url.path,
        ),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            error="An unexpected error occurred",
            detail="Please contact support if this issue persists",
            path=request.url.path,
        ),
    )

# ==================== Entry Point ====================
if __name__ == "__main__":
    import uvicorn

    # Security: Restrict bind address in production to localhost; allow 0.0.0.0 only in development
    # For production, use a reverse proxy (nginx/load balancer) to expose the service
    if ENVIRONMENT == "development":
        host = os.getenv("HOST", "127.0.0.1")  # Default to localhost for safety
    else:
        host = os.getenv("HOST", "127.0.0.1")  # Production must explicitly set HOST to bind
    port = int(os.getenv("PORT", 8000))

    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=ENVIRONMENT == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
