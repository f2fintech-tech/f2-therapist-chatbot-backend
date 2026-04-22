"""
Financial Therapist Chatbot Backend
FastAPI application with Anthropic Claude 3.5 Sonnet integration
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import logging

# Import routers
from src.routers import health, chat, conversations
from src.models import init_db

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== FastAPI Initialization ====================
app = FastAPI(
    title="Financial Therapist Chatbot",
    description="AI-powered financial therapy chatbot backend with Anthropic Claude 3.5 Sonnet",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# ==================== CORS Configuration ====================
# Get allowed origins from environment variable
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")

# For production, default to no origins (explicitly set required)
if ENVIRONMENT == "production":
    if os.getenv("ALLOWED_ORIGINS") is None:
        logger.warning("ALLOWED_ORIGINS not set in production. CORS disabled for safety.")
        ALLOWED_ORIGINS = []

logger.info(f"Environment: {ENVIRONMENT}")
logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

# Configure CORS with secure settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# ==================== Database Initialization ====================
init_db()

# ==================== Include Routers ====================
# Health check routes
app.include_router(health.router)

# Chat routes (v1 API)
app.include_router(chat.router, prefix="/api/v1")

# Conversation management routes (v1 API)
app.include_router(conversations.router, prefix="/api/v1")

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
        "api_base": "/api/v1"
    }

# ==================== Startup/Shutdown Events ====================
@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("=" * 60)
    logger.info("Starting Financial Therapist Chatbot Backend")
    logger.info("=" * 60)
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Anthropic API configured: {bool(os.getenv('ANTHROPIC_API_KEY'))}")
    logger.info(f"Database configured: {bool(os.getenv('DATABASE_URL'))}")
    logger.info("API Documentation available at: /docs")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("=" * 60)
    logger.info("Shutting down Financial Therapist Chatbot Backend")
    logger.info("=" * 60)

# ==================== Global Error Handler ====================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return {
        "error": "An unexpected error occurred",
        "detail": "Please contact support if this issue persists"
    }

# ==================== Entry Point ====================
if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=ENVIRONMENT == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )