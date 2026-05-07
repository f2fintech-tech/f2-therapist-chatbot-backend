"""
Request logging middleware for FastAPI.
Logs all incoming requests and outgoing responses.
"""

import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all HTTP requests and responses.
    Tracks request duration, status codes, and request/response sizes.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process the request, time it, and log details.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler

        Returns:
            The HTTP response with logging metadata
        """

        # Start timer
        start_time = time.time()

        # Extract request details
        method = request.method
        path = request.url.path

        # Log incoming request
        logger.info("Incoming Request: %s %s", method, path)

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Extract response details
            status_code = response.status_code

            # Log response
            log_level = "INFO" if 200 <= status_code < 400 else "WARNING"

            log_message = (
                f"{method} {path} | "
                f"Status: {status_code} | "
                f"Duration: {duration:.3f}s"
            )

            if log_level == "INFO":
                logger.info(log_message)
            else:
                logger.warning(log_message)

            # Add custom headers for tracing
            response.headers["X-Process-Time"] = str(duration)

            return response

        except Exception as e:
            # Calculate duration on error
            duration = time.time() - start_time

            logger.error(
                f"{method} {path} | "
                f"Error: {str(e)} | "
                f"Duration: {duration:.3f}s",
                exc_info=True
            )

            raise

class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs security-related events.
    Tracks authentication failures, suspicious patterns, etc.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Log security-related information from requests.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler

        Returns:
            The HTTP response
        """

        # Check for suspicious patterns
        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"

        # Log authorization attempts
        if "authorization" in request.headers:
            logger.debug(f"Authorization attempt from {client_ip}")

        # Log admin/sensitive endpoint access
        sensitive_paths = ["/admin", "/api/v1/admin", "/api/v1/users"]
        if any(path.startswith(sp) for sp in sensitive_paths):
            logger.info(f"Sensitive endpoint access: {method} {path} from {client_ip}")

        # Log unusual HTTP methods on public endpoints
        if method not in ["GET", "POST", "PUT", "DELETE"] and not path.startswith("/api"):
            logger.warning(f"Unusual HTTP method: {method} {path} from {client_ip}")

        response = await call_next(request)

        # Log failed authentication (401, 403)
        if response.status_code in [401, 403]:
            logger.warning(f"Auth failure: {method} {path} from {client_ip} - Status: {response.status_code}")

        return response
