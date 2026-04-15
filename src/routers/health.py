from fastapi import APIRouter
from pydantic import BaseModel
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Health"])

# ==================== Models ====================
class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    service: str
    database_configured: bool
    anthropic_api_configured: bool

class StatusResponse(BaseModel):
    """Service status response model."""
    service: str
    status: str
    version: str
    environment: str

# ==================== Routes ====================
@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns status of the service and configuration.
    """
    return HealthCheckResponse(
        status="healthy",
        version="0.1.0",
        service="Financial Therapist Chatbot Backend",
        database_configured=bool(os.getenv("DATABASE_URL")),
        anthropic_api_configured=bool(os.getenv("ANTHROPIC_API_KEY"))
    )

@router.get("/status", response_model=StatusResponse)
async def get_status():
    """
    Get service status and configuration info.
    
    Returns current service status and environment information.
    """
    return StatusResponse(
        service="Financial Therapist Chatbot",
        status="running",
        version="0.1.0",
        environment=os.getenv("ENVIRONMENT", "development")
    )

@router.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes or load balancers.
    
    Returns true if service is ready to accept requests.
    """
    return {
        "ready": True,
        "service": "Financial Therapist Chatbot Backend"
    }