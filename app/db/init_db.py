"""Database initialization."""
from app.db.base import Base
from app.db.session import engine
from app.logging import get_logger

logger = get_logger(__name__)


async def create_tables():
    """Create all database tables."""
    try:
        async with engine.begin() as conn:
            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Failed to create database tables", extra={"error": str(e)})
        raise


async def drop_tables():
    """Drop all database tables."""
    try:
        async with engine.begin() as conn:
            logger.warning("Dropping database tables...")
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error("Failed to drop database tables", extra={"error": str(e)})
        raise