"""Decorators and FastAPI dependencies for authentication and authorization.

These decorators are intended for use with API handlers that receive the
authenticated user as a ``current_user`` kwarg (a dict at minimum).
They work independently of any specific web framework.

FastAPI dependencies (get_current_user, require_role, etc.) are also provided
for router-level dependency injection.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lakenterprises.config import get_settings

from .exceptions import InsufficientPermissionsError
from .service import AuthService

logger = logging.getLogger(__name__)

# Security scheme for Swagger UI
security_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Framework-agnostic decorators
# ---------------------------------------------------------------------------


def require_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that checks if ``current_user`` is present and authenticated.

    Raises ``InsufficientPermissionsError`` when the user is missing or
    not authenticated.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        user = kwargs.get("current_user")
        if not user or not user.get("is_authenticated"):
            raise InsufficientPermissionsError(
                "Authentication required",
                user.get("id") if user else None,
            )
        return func(*args, **kwargs)

    return wrapper


def require_permission(permission: str) -> Callable[..., Any]:
    """Decorator or dependency that checks if ``current_user`` has the required permission."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = kwargs.get("current_user")
            if not user:
                raise InsufficientPermissionsError(
                    f"Permission required: {permission}", None
                )
            permissions = user.get("permissions", [])
            if permission not in permissions:
                raise InsufficientPermissionsError(
                    f"Permission '{permission}' required",
                    user.get("id"),
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def admin_only(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that restricts access to users with the ``ADMIN`` role.

    Raises ``InsufficientPermissionsError`` when the user is missing or
    does not hold the ``ADMIN`` role.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        user = kwargs.get("current_user")
        if not user:
            raise InsufficientPermissionsError("Admin access required", None)
        roles = user.get("roles", [])
        if "ADMIN" not in roles and "admin" not in [r.lower() for r in roles]:
            raise InsufficientPermissionsError("Admin role required", user.get("id"))
        return func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------

_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Return the global AuthService instance."""
    global _auth_service
    if _auth_service is None:
        settings = get_settings()
        secret = (
            settings.jwt_secret
            or "lakenterprises-default-secret-key-change-in-production"
        )
        _auth_service = AuthService(
            secret_key=secret,
            algorithm=settings.jwt_algorithm,
            access_token_expire_minutes=settings.jwt_expiry_minutes,
        )
    return _auth_service


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """FastAPI dependency to extract and decode the current user from Bearer token."""
    token: Optional[str] = None
    if credentials:
        token = credentials.credentials
    else:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = auth_service.decode_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    roles = payload.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]

    user_info = {
        "id": payload.get("sub"),
        "username": payload.get("username", payload.get("sub")),
        "email": payload.get("email", ""),
        "roles": roles,
        "permissions": payload.get("permissions", []),
        "is_authenticated": True,
    }

    # Store user_id on request state for audit middleware
    request.state.user_id = user_info["id"]
    return user_info


def require_role(*allowed_roles: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """FastAPI dependency factory to enforce user role membership."""
    allowed = {r.lower() for r in allowed_roles}

    async def role_checker(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        user_roles = {r.lower() for r in current_user.get("roles", [])}
        if not user_roles.intersection(allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: required role in {list(allowed_roles)}, got {current_user.get('roles', [])}",
            )
        return current_user

    return role_checker
