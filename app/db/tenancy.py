"""Tenancy context management."""
from contextvars import ContextVar
from typing import Optional
from uuid import UUID

# Context variable to store the current tenant ID
tenant_ctx: ContextVar[Optional[UUID]] = ContextVar("tenant_id", default=None)


def get_current_tenant() -> Optional[UUID]:
    """Get the current tenant ID from context."""
    return tenant_ctx.get()


def set_current_tenant(tenant_id: UUID) -> None:
    """Set the current tenant ID in context."""
    tenant_ctx.set(tenant_id)


def clear_current_tenant() -> None:
    """Clear the current tenant ID from context."""
    tenant_ctx.set(None)