"""API dependencies."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.db.tenancy import set_current_tenant
from app.logging import get_logger

logger = get_logger(__name__)


def require_tenant(
    x_tenant_id: Annotated[str | None, Header(alias="x-tenant-id", description="Tenant ID (UUID format)")] = None
) -> UUID:
    """
    Dependency to enforce tenant ID presence and validation.
    
    Args:
        x_tenant_id: Tenant ID from the x-tenant-id header
        
    Returns:
        Validated and normalized tenant UUID
        
    Raises:
        HTTPException: 400 if header is missing, 422 if invalid UUID
    """
    if not x_tenant_id:
        logger.warning("Missing x-tenant-id header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="x-tenant-id header is required"
        )
    
    try:
        # Parse and normalize the UUID (converts to lowercase)
        tenant_id = UUID(x_tenant_id.strip())
        
        # Store in context for the duration of the request
        set_current_tenant(tenant_id)
        
        logger.info("Tenant context set", extra={"tenant_id": str(tenant_id)})
        
        # Verify it was set correctly
        from app.db.tenancy import get_current_tenant
        current = get_current_tenant()
        logger.info("Tenant context verification", extra={"set_tenant": str(tenant_id), "current_tenant": str(current)})
        
        return tenant_id
        
    except ValueError as e:
        logger.warning("Invalid tenant ID format", extra={"provided_id": x_tenant_id})
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid tenant ID format: {str(e)}"
        )