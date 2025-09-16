"""Health check endpoint."""
from fastapi import APIRouter

from app.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "service": "fastapi-tenant-app",
        "version": "0.1.0"
    }