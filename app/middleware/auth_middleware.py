from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging
import time

logger = logging.getLogger(__name__)

# Routes that do NOT require authentication
PUBLIC_ROUTES = {
    "/api/v1/auth/login",
    "/api/v1/auth/send-otp",
    "/api/v1/auth/verify-otp",
    "/api/v1/auth/refresh",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/",
    "/ws/notifications",
}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each request with timing information."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = (time.perf_counter() - start) * 1000
        logger.info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duration:.1f}ms)"
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
