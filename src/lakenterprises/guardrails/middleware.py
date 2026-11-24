"""ASGI middleware for PII & secret inspection and sanitization."""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lakenterprises.guardrails.pii_scrubber import (PIIScrubber,
                                                    default_scrubber)

logger = logging.getLogger(__name__)


class PIIScrubberMiddleware(BaseHTTPMiddleware):
    """Inspects incoming requests and outgoing responses, redacting secrets and PII."""

    def __init__(
        self,
        app: object,
        scrubber: Optional[PIIScrubber] = None,
        block_on_secret: bool = False,
        exempt_paths: Optional[List[str]] = None,
    ) -> None:
        super().__init__(app)
        self.scrubber = scrubber or default_scrubber
        self.block_on_secret = block_on_secret
        self.exempt_paths = exempt_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in self.exempt_paths):
            return await call_next(request)

        # Inspect request query string
        query_str = str(request.url.query)
        if query_str:
            res = self.scrubber.scrub_text(query_str)
            if self.block_on_secret and res.contains_secrets:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "detail": (
                            "Request rejected: plaintext credentials or private keys "
                            "detected in query parameters."
                        )
                    },
                )

        response = await call_next(request)
        return response
