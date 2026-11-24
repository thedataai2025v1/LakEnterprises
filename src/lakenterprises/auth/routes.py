"""FastAPI authentication and authorization routes.

Provides endpoints for login, token refresh, logout, current user profile,
and demo tokens for viewer, analyst, and admin roles.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from lakenterprises.auth.middleware import get_auth_service, get_current_user
from lakenterprises.auth.service import AuthService
from lakenterprises.db import get_db_session
from lakenterprises.repositories import UserRepository
from lakenterprises.services.audit import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username_or_email: str = Field(..., description="User's username or email address")
    password: str = Field(..., description="User password")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user: Optional[dict[str, Any]] = None


class UserProfileResponse(BaseModel):
    id: str
    username: str
    email: str
    roles: List[str]
    permissions: List[str]
    is_authenticated: bool = True


class DemoTokensResponse(BaseModel):
    viewer: str
    analyst: str
    admin: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Demo Roles & Permissions Definition
# ---------------------------------------------------------------------------

DEMO_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "viewer": [
        "view_documents",
        "read_document",
        "create_reports",
    ],
    "analyst": [
        "view_documents",
        "read_document",
        "create_document",
        "manage_documents",
        "create_session",
        "read_session",
        "create_reports",
        "export_data",
    ],
    "admin": [
        "create_user",
        "read_user",
        "update_user",
        "delete_user",
        "user_management",
        "create_role",
        "read_role",
        "update_role",
        "delete_role",
        "manage_roles",
        "create_document",
        "read_document",
        "update_document",
        "delete_document",
        "view_documents",
        "manage_documents",
        "create_session",
        "read_session",
        "update_session",
        "delete_session",
        "view_sessions",
        "view_audit_logs",
        "create_reports",
        "export_data",
        "system_operations",
    ],
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticate user with username/email and password."""
    session = get_db_session()
    user_repo = UserRepository(session)
    user = None

    if "@" in req.username_or_email:
        user = user_repo.get_by_email(req.username_or_email)
    else:
        user = user_repo.get_by_username(req.username_or_email)

    audit_service = AuditService(db_session=session)
    client_ip = request.client.host if request.client else None

    # Check credentials
    verified = False
    if user and user.password_hash:
        try:
            verified = auth_service.verify_password(req.password, user.password_hash)
        except Exception:
            # Fallback for PBKDF2 format: salt_hex (64) + key_hex (64)
            import hashlib

            stored = user.password_hash
            if len(stored) >= 128:
                salt_hex = stored[:64]
                key_hex = stored[64:]
                try:
                    key = bytes.fromhex(key_hex)
                    expected = hashlib.pbkdf2_hmac(
                        "sha256",
                        req.password.encode(),
                        bytes.fromhex(salt_hex),
                        100_000,
                    )
                    verified = key == expected
                except Exception:
                    verified = False

    if not user or not verified:
        audit_service.log(
            action="LOGIN_FAILED",
            user_id=user.id if user else None,
            details={"username_or_email": req.username_or_email},
            severity="WARNING",
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    roles = [r.name for r in user.roles]
    permissions = []
    for r in user.roles:
        for p in r.permissions:
            if p.name not in permissions:
                permissions.append(p.name)

    access_token = auth_service.create_access_token(
        user_id=user.id,
        permissions=permissions,
        extra_claims={
            "username": user.username,
            "email": user.email,
            "roles": roles,
        },
    )
    refresh_token = auth_service.create_refresh_token(user_id=user.id)

    # Record login
    audit_service.log(
        action="LOGIN_SUCCESS",
        user_id=user.id,
        details={"username": user.username},
        severity="INFO",
        ip_address=client_ip,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=auth_service.access_token_expire_minutes * 60,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "roles": roles,
            "permissions": permissions,
        },
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token_endpoint(
    req: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Issue a new access token using a valid refresh token."""
    session = get_db_session()
    try:
        new_access, new_refresh = auth_service.refresh(req.refresh_token, session)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired refresh token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=auth_service.access_token_expire_minutes * 60,
    )


@router.post("/logout")
def logout(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """Revoke the current user's session token."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    session = get_db_session()

    if token:
        import hashlib

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        auth_service.revoke_token(token_hash, session)

    audit_service = AuditService(db_session=session)
    client_ip = request.client.host if request.client else None
    audit_service.log(
        action="LOGOUT",
        user_id=current_user["id"],
        details={"username": current_user.get("username")},
        severity="INFO",
        ip_address=client_ip,
    )

    return {"detail": "Logged out successfully"}


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UserProfileResponse:
    """Return profile, roles, and permissions of the authenticated user."""
    return UserProfileResponse(
        id=current_user["id"],
        username=current_user.get("username", ""),
        email=current_user.get("email", ""),
        roles=current_user.get("roles", []),
        permissions=current_user.get("permissions", []),
        is_authenticated=True,
    )


@router.post("/demo/{role}", response_model=TokenResponse)
def get_demo_token(
    role: str,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Generate a signed demo token for testing or evaluation (viewer, analyst, admin)."""
    role_lower = role.lower()
    if role_lower not in DEMO_ROLE_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid demo role: '{role}'. Must be one of {list(DEMO_ROLE_PERMISSIONS.keys())}",
        )

    demo_user_id = f"demo-{role_lower}-user"
    demo_username = f"demo_{role_lower}"
    demo_email = f"{role_lower}@lakenterprises.demo"
    permissions = DEMO_ROLE_PERMISSIONS[role_lower]

    access_token = auth_service.create_access_token(
        user_id=demo_user_id,
        permissions=permissions,
        extra_claims={
            "username": demo_username,
            "email": demo_email,
            "roles": [role_lower],
            "is_demo": True,
        },
    )
    refresh_token = auth_service.create_refresh_token(user_id=demo_user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=auth_service.access_token_expire_minutes * 60,
        user={
            "id": demo_user_id,
            "username": demo_username,
            "email": demo_email,
            "roles": [role_lower],
            "permissions": permissions,
        },
    )


@router.get("/demo-tokens", response_model=DemoTokensResponse)
def get_all_demo_tokens(
    auth_service: AuthService = Depends(get_auth_service),
) -> DemoTokensResponse:
    """Return ready-to-use demo tokens for all three platform roles (viewer, analyst, admin)."""
    tokens: dict[str, str] = {}
    for r in ["viewer", "analyst", "admin"]:
        tok = auth_service.create_access_token(
            user_id=f"demo-{r}-user",
            permissions=DEMO_ROLE_PERMISSIONS[r],
            extra_claims={
                "username": f"demo_{r}",
                "email": f"{r}@lakenterprises.demo",
                "roles": [r],
                "is_demo": True,
            },
        )
        tokens[r] = tok

    return DemoTokensResponse(
        viewer=tokens["viewer"],
        analyst=tokens["analyst"],
        admin=tokens["admin"],
        token_type="bearer",
    )
