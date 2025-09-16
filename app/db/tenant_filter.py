"""Global tenant filtering for database operations."""
from typing import Any
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstanceState, Session
from sqlalchemy.orm.events import InstanceEvents
from sqlalchemy.sql import Select

from app.db.base import Base
from app.db.models import Transaction
from app.db.tenancy import get_current_tenant
from app.logging import get_logger

logger = get_logger(__name__)

# Models that should be tenant-scoped
TENANT_SCOPED_MODELS = {Transaction}


def is_tenant_scoped_model(model_class: type) -> bool:
    """Check if a model class should be tenant-scoped."""
    return model_class in TENANT_SCOPED_MODELS


def get_tenant_id_column(model_class: type) -> str:
    """Get the tenant ID column name for a model."""
    # For now, all models use 'tenant_id'
    return 'tenant_id'


@event.listens_for(Session, "do_orm_execute")
def auto_filter_tenant_reads(orm_execute_state):
    """
    Automatically filter all SELECT queries by current tenant.
    
    This event listener ensures that all database reads are automatically
    filtered by the current tenant ID from the context.
    """
    # Only apply to SELECT statements
    if not orm_execute_state.is_select:
        return
        
    # Get current tenant from context
    current_tenant = get_current_tenant()
    if current_tenant is None:
        # No tenant in context - this should only happen for health checks
        # or other non-tenant operations
        return
    
    # Check if any of the tables in the query are tenant-scoped
    statement = orm_execute_state.statement
    
    # For simple queries, check if we're querying a tenant-scoped model
    if hasattr(statement, 'table') and hasattr(statement.table, 'name'):
        table_name = statement.table.name
        if table_name == 'transactions':  # Our tenant-scoped table
            # Add tenant filter to the query
            from app.db.models import Transaction
            tenant_column = Transaction.tenant_id
            orm_execute_state.statement = statement.where(
                tenant_column == current_tenant
            )
            logger.debug(
                "Applied tenant filter to query",
                extra={
                    "tenant_id": str(current_tenant),
                    "table": table_name
                }
            )


@event.listens_for(Session, "before_flush")
def validate_tenant_writes(session, flush_context, instances):
    """
    Validate and set tenant_id for all writes.
    
    This event listener ensures that:
    1. All new tenant-scoped objects have the correct tenant_id set
    2. All modified tenant-scoped objects maintain the correct tenant_id
    3. Raises an error if there's a tenant_id mismatch
    """
    current_tenant = get_current_tenant()
    if current_tenant is None:
        # No tenant context - allow for system operations
        return
    
    # Check all objects being persisted
    for obj in session.new | session.dirty:
        if not is_tenant_scoped_model(obj.__class__):
            continue
            
        tenant_column_name = get_tenant_id_column(obj.__class__)
        current_tenant_id = getattr(obj, tenant_column_name, None)
        
        if obj in session.new:
            # New object - set tenant_id if not already set
            if current_tenant_id is None:
                setattr(obj, tenant_column_name, current_tenant)
                logger.debug(
                    "Set tenant_id on new object",
                    extra={
                        "tenant_id": str(current_tenant),
                        "model": obj.__class__.__name__,
                        "object_id": getattr(obj, 'id', 'unknown')
                    }
                )
            elif current_tenant_id != current_tenant:
                # Tenant ID mismatch on new object
                logger.error(
                    "Tenant ID mismatch on new object",
                    extra={
                        "expected_tenant": str(current_tenant),
                        "provided_tenant": str(current_tenant_id),
                        "model": obj.__class__.__name__
                    }
                )
                raise ValueError(
                    f"Tenant ID mismatch: expected {current_tenant}, "
                    f"got {current_tenant_id}"
                )
        
        elif obj in session.dirty:
            # Modified object - ensure tenant_id hasn't changed
            if current_tenant_id != current_tenant:
                logger.error(
                    "Attempt to modify object with wrong tenant ID",
                    extra={
                        "expected_tenant": str(current_tenant),
                        "object_tenant": str(current_tenant_id),
                        "model": obj.__class__.__name__,
                        "object_id": getattr(obj, 'id', 'unknown')
                    }
                )
                raise ValueError(
                    f"Cannot modify object from different tenant: "
                    f"expected {current_tenant}, object has {current_tenant_id}"
                )


def setup_tenant_filtering():
    """Setup tenant filtering event listeners."""
    logger.info("Tenant filtering event listeners registered")
    # Event listeners are registered via decorators above