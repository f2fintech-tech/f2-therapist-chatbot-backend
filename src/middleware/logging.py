"""
Request logging middleware for FastAPI.
Logs all incoming requests and outgoing responses.
"""

import logging
import time

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """
    Middleware that logs all HTTP requests and responses.
    Tracks request duration, status codes, and request/response sizes.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "")

        logger.info("Incoming Request: %s %s", method, path)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration = time.time() - start_time
                status_code = message.get("status", 200)

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

                # Add custom headers for tracing (X-Process-Time)
                headers = list(message.get("headers", []))
                headers.append((b"x-process-time", str(duration).encode()))
                message["headers"] = headers

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"{method} {path} | "
                f"Error: {str(e)} | "
                f"Duration: {duration:.3f}s",
                exc_info=True
            )
            raise


class SecurityLoggingMiddleware:
    """
    Middleware that logs security-related events.
    Tracks authentication failures, suspicious patterns, etc.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "UNKNOWN")

        # Safe extraction of client IP
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        headers_dict = dict(scope.get("headers", []))

        # Check X-Forwarded-For if available
        forwarded_for = headers_dict.get(b"x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.decode().split(",")[0].strip()

        # Log authorization attempts
        if b"authorization" in headers_dict:
            logger.debug(f"Authorization attempt from {client_ip}")

        # Log admin/sensitive endpoint access
        sensitive_paths = ["/admin", "/api/v1/admin", "/api/v1/users"]
        if any(path.startswith(sp) for sp in sensitive_paths):
            logger.info(f"Sensitive endpoint access: {method} {path} from {client_ip}")

        # Log unusual HTTP methods on public endpoints
        if method not in ["GET", "POST", "PUT", "DELETE"] and not path.startswith("/api"):
            logger.warning(f"Unusual HTTP method: {method} {path} from {client_ip}")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
                if status_code in [401, 403]:
                    logger.warning(f"Auth failure: {method} {path} from {client_ip} - Status: {status_code}")
            await send(message)

        await self.app(scope, receive, send_wrapper)

