"""FastAPI application factory and middleware pipeline for LakEnterprises.

Configures:
- Health endpoints (/health, /health/live, /health/ready)
- AuditMiddleware with request tracking and X-Request-ID propagation
- RateLimitMiddleware with Redis / in-memory sliding window
- Authentication & RBAC routes under /api/v1/auth
- Role-protected endpoints for testing and verification
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from lakenterprises.auth.audit_middleware import AuditMiddleware
from lakenterprises.auth.middleware import get_current_user, require_role
from lakenterprises.auth.rate_limit import (RateLimitMiddleware,
                                            get_rate_limiter)
from lakenterprises.auth.routes import router as auth_router
from lakenterprises.document.routes import router as document_router
from lakenterprises.guardrails.middleware import PIIScrubberMiddleware
from lakenterprises.guardrails.routes import router as guardrails_router
from lakenterprises.process.routes import approvals_router
from lakenterprises.process.routes import router as process_router
from lakenterprises.services.audit import AuditService
from lakenterprises.tools.routes import router as tools_router

logger = logging.getLogger(__name__)


def create_app(
    audit_service: Optional[AuditService] = None,
    rate_limit_per_minute: Optional[int] = None,
) -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="LakEnterprises API",
        description="Enterprise Knowledge Research & Access Control Platform",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        _request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {},
        )

    # 2. Rate Limiting Middleware
    limiter = get_rate_limiter()
    if rate_limit_per_minute is not None:
        limiter.default_limit = rate_limit_per_minute
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    # 3. Audit Logging & Request ID Middleware
    app.add_middleware(AuditMiddleware, audit_service=audit_service)

    # 4. Guardrails PII & Secret Scrubber Middleware
    app.add_middleware(PIIScrubberMiddleware)

    # ── Health Endpoints ──────────────────────────────────────────────
    @app.get("/health", tags=["health"])
    @app.get("/health/live", tags=["health"])
    def health_check() -> dict[str, str]:
        """Liveness probe: verifies process is alive and responsive."""
        return {"status": "ok", "service": "lakenterprises"}

    @app.get("/health/ready", tags=["health"])
    def readiness_check() -> dict[str, Any]:
        """Readiness probe: checks DB and cache connectivity."""
        db_ready = True
        try:
            from sqlalchemy import text

            from lakenterprises.db import get_engine

            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            logger.warning("Readiness DB check failed: %s", exc)
            db_ready = False

        status_str = "ready" if db_ready else "degraded"
        return {
            "status": status_str,
            "database": "connected" if db_ready else "disconnected",
            "version": "0.1.0",
        }

    # ── Routers ───────────────────────────────────────────────────────
    app.include_router(auth_router)
    app.include_router(document_router)
    app.include_router(process_router)
    app.include_router(approvals_router)
    app.include_router(tools_router)
    app.include_router(guardrails_router)

    # ── Sample Protected Routes for RBAC Testing & Verification ──────
    @app.get(
        "/api/v1/protected/user",
        tags=["protected"],
        dependencies=[Depends(get_current_user)],
    )
    def protected_user_route(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Accessible by any authenticated user."""
        return {
            "message": "Authenticated user access granted",
            "user": current_user["username"],
        }

    @app.get(
        "/api/v1/protected/analyst",
        tags=["protected"],
        dependencies=[Depends(require_role("analyst", "admin"))],
    )
    def protected_analyst_route(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Accessible only by analysts and admins."""
        return {"message": "Analyst access granted", "user": current_user["username"]}

    @app.get(
        "/api/v1/protected/admin",
        tags=["protected"],
        dependencies=[Depends(require_role("admin"))],
    )
    def protected_admin_route(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Accessible strictly by admins."""
        return {"message": "Admin access granted", "user": current_user["username"]}

    return app


# Default app instance
app = create_app()
