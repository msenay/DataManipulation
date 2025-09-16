"""Global exception handlers."""
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.logging import get_logger

logger = get_logger(__name__)


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    logger.warning(
        "Validation error",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": exc.errors()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation failed",
            "errors": exc.errors()
        }
    )


async def value_error_exception_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions (e.g., from tenant validation)."""
    error_msg = str(exc)
    
    # Check if it's a tenant-related error (from write guard or validation)
    if any(keyword in error_msg.lower() for keyword in ["tenant", "mismatch", "write guard"]):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        log_level = "warning"
        detail = f"Tenant validation error: {error_msg}"
    # Check if it's a date range validation error
    elif "start_ts" in error_msg and "end_ts" in error_msg:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        log_level = "warning"
        detail = error_msg
    else:
        status_code = status.HTTP_400_BAD_REQUEST
        log_level = "warning"
        detail = error_msg
    
    getattr(logger, log_level)(
        "Value error handled",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": error_msg,
            "status_code": status_code
        }
    )
    
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail}
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle SQLAlchemy database errors."""
    logger.error(
        "Database error",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
            "error_type": type(exc).__name__
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error occurred"}
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other unhandled exceptions."""
    logger.error(
        "Unhandled exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
            "error_type": type(exc).__name__
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with consistent logging."""
    # Don't log 404s for cross-tenant access (they're expected)
    if exc.status_code == 404:
        logger.debug(
            "HTTP 404 response",
            extra={
                "path": request.url.path,
                "method": request.method,
                "detail": exc.detail
            }
        )
    elif exc.status_code >= 500:
        logger.error(
            "HTTP server error",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": exc.status_code,
                "detail": exc.detail
            }
        )
    elif exc.status_code >= 400:
        logger.warning(
            "HTTP client error",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": exc.status_code,
                "detail": exc.detail
            }
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )