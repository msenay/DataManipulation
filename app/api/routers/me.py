"""Me endpoint for tenant information."""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import require_tenant
from app.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/me")
async def get_me(tenant_id: UUID = Depends(require_tenant)):
    """
    Get current tenant information.
    
    Returns the normalized tenant ID from the request context.
    """
    logger.info("Me endpoint accessed", extra={"tenant_id": str(tenant_id)})
    return {"tenant_id": str(tenant_id)}