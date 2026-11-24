"""Audit and Request-ID middleware for FastAPI (pure ASGI).

Captures request ID (X-Request-ID), measures execution latency,
and logs HTTP operations into AuditService with zero deadlock risk.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lakenterprises.services.audit import AuditService

logger = logging.getLogger(__name__)


class AuditMiddleware:
    """Pure ASGI middleware that tracks request ID, duration, and logs requests to AuditService."""

    def __init__(
        self,
        app: ASGIApp,
        audit_service: Optional[AuditService] = None,
        exempt_paths: Optional[list[str]] = None,
    ) -> None:
        self.app = app
        self.audit_service = audit_service or AuditService()
        self.exempt_paths = exempt_paths or [
            "/health/live",
            "/health/ready",
            "/docs",
            "/openapi.json",
        ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get("X-Request-ID") or str(uuid.uuid4())
        path = scope.get("path", "")
        method = scope.get("method", "")

        client = scope.get("client")
        client_ip = client[0] if client else None

        user_id = headers.get("X-User-ID")

        start_time = time.perf_counter()
        status_code = 200

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
                mutable_headers = MutableHeaders(scope=message)
                mutable_headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if not any(path.startswith(p) for p in self.exempt_paths):
                self.audit_service.log(
                    action="HTTP_REQUEST_ERROR",
                    user_id=user_id,
                    details={
                        "method": method,
                        "path": path,
                        "duration_ms": duration_ms,
                        "error": str(exc),
                        "request_id": request_id,
                    },
                    severity="ERROR",
                    ip_address=client_ip,
                )
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        if not any(path.startswith(p) for p in self.exempt_paths):
            severity = "WARNING" if status_code >= 400 else "INFO"
            self.audit_service.log(
                action="HTTP_REQUEST",
                user_id=user_id,
                details={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "request_id": request_id,
                },
                severity=severity,
                ip_address=client_ip,
            )
