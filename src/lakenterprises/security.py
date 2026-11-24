"""Production Security Headers Middleware.

Injects enterprise-grade HTTP security headers:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security: max-age=31536000; includeSubDomains
- Content-Security-Policy (CSP)
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: geolocation=(), camera=(), microphone=()
"""

from __future__ import annotations

from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Starlette middleware to append security headers to all HTTP responses."""

    def __init__(
        self,
        app: Callable,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,
        include_subdomains: bool = True,
    ) -> None:
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_header = f"max-age={hsts_max_age}" + (
            "; includeSubDomains" if include_subdomains else ""
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Standard OWASP security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Content-Security-Policy (allows Swagger/Redoc UI CDNs while securing API)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none';"
        )

        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = self.hsts_header

        return response
