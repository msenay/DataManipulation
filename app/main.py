"""FastAPI application main module."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.api.routers import health, me, transactions, import_transactions, metrics
from app.config import settings
from app.db.init_db import create_tables
from app.db import models  # Import to register models
from app.db.tenant_filter import setup_tenant_filtering
from app.logging import setup_logging, get_logger
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.exceptions import (
    general_exception_handler,
    http_exception_handler,
    sqlalchemy_exception_handler,
    validation_exception_handler,
    value_error_exception_handler,
)

# Setup logging before creating the app
setup_logging()
logger = get_logger(__name__)

# Create FastAPI application
app = FastAPI(
    title="FastAPI Tenant App",
    description="FastAPI application with multi-tenancy support",
    version="0.1.0",
    debug=settings.debug,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add global exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(ValueError, value_error_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
# Health router - no tenant requirement
app.include_router(
    health.router,
    prefix=settings.api_v1_prefix,
    tags=["health"]
)

# Protected routers - require tenant
from fastapi import Depends
from app.api.deps import require_tenant

app.include_router(
    me.router,
    prefix=settings.api_v1_prefix,
    tags=["tenant"]
)

app.include_router(
    transactions.router,
    prefix=settings.api_v1_prefix,
    tags=["transactions"]
)

app.include_router(
    import_transactions.router,
    prefix=settings.api_v1_prefix,
    tags=["import"]
)

app.include_router(
    metrics.router,
    prefix=settings.api_v1_prefix,
    tags=["metrics"]
)


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("Starting FastAPI Tenant App")
    
    # Setup tenant filtering
    setup_tenant_filtering()
    
    # Initialize database tables
    await create_tables()


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Shutting down FastAPI Tenant App")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_config=None,  # Use our custom logging
    )