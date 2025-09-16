"""Request logging middleware."""
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.tenancy import get_current_tenant
from app.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests with timing and tenant context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log details."""
        start_time = time.time()
        
        # Extract request details
        method = request.method
        url = str(request.url)
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Process the request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Get tenant context if available
        tenant_id = get_current_tenant()
        
        # Log the request
        log_data = {
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "client_ip": client_ip,
            "user_agent": user_agent
        }
        
        # Add tenant context if available
        if tenant_id:
            log_data["tenant_id"] = str(tenant_id)
        
        # Log at appropriate level based on status code
        if response.status_code >= 500:
            logger.error("HTTP request completed", extra=log_data)
        elif response.status_code >= 400:
            logger.warning("HTTP request completed", extra=log_data)
        else:
            logger.info("HTTP request completed", extra=log_data)
        
        return response