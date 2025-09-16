"""Database session management."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    # For SQLite, we need special configuration
    poolclass=StaticPool if settings.is_sqlite else None,
    connect_args={"check_same_thread": False} if settings.is_sqlite else {},
)

# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncSession:
    """
    Get database session dependency.
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            logger.debug("Database session created")
            yield session
        except Exception as e:
            logger.error("Database session error", extra={"error": str(e)})
            await session.rollback()
            raise
        finally:
            await session.close()
            logger.debug("Database session closed")


async def get_tenant_db_session() -> AsyncSession:
    """
    Get database session dependency with tenant context validation.
    
    This dependency ensures that a tenant context is set before
    allowing database operations.
    
    Yields:
        AsyncSession: Database session with tenant context
        
    Raises:
        HTTPException: If no tenant context is set
    """
    from app.db.tenancy import get_current_tenant
    from fastapi import HTTPException, status
    
    current_tenant = get_current_tenant()
    if current_tenant is None:
        logger.error("Database session requested without tenant context")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error: No tenant context set"
        )
    
    async with AsyncSessionLocal() as session:
        try:
            logger.debug(
                "Tenant-scoped database session created",
                extra={"tenant_id": str(current_tenant)}
            )
            yield session
        except Exception as e:
            logger.error(
                "Tenant-scoped database session error",
                extra={"error": str(e), "tenant_id": str(current_tenant)}
            )
            await session.rollback()
            raise
        finally:
            await session.close()
            logger.debug(
                "Tenant-scoped database session closed",
                extra={"tenant_id": str(current_tenant)}
            )