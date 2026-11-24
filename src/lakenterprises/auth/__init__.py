"""Authentication, authorization, rate limiting, and audit for LakEnterprises."""

from .audit_middleware import AuditMiddleware
from .middleware import (admin_only, get_auth_service, get_current_user,
                         require_auth, require_permission, require_role)
from .rate_limit import (RateLimitMiddleware, SlidingWindowRateLimiter,
                         get_rate_limiter)
from .routes import router as auth_router
from .service import AuthService

__all__ = [
    "AuthService",
    "AuditMiddleware",
    "RateLimitMiddleware",
    "SlidingWindowRateLimiter",
    "admin_only",
    "auth_router",
    "get_auth_service",
    "get_current_user",
    "get_rate_limiter",
    "require_auth",
    "require_permission",
    "require_role",
]
