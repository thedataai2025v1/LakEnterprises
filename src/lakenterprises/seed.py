"""Seed data loader for the LakEnterprises platform.

Populates the database with default roles, permissions,
role-permission assignments, and a bootstrap admin user.
Every operation is idempotent – running it multiple times
is safe because existing records are skipped.
"""

from __future__ import annotations

import hashlib
import logging
import os
from enum import Enum

from sqlalchemy import insert, select

from lakenterprises.config import get_settings
from lakenterprises.db import get_db_session, init_db
from lakenterprises.models.entities import (Permission, Role, User,
                                            role_permission, role_user)

logger = logging.getLogger(__name__)


# ─── Enums (task-specified values that extend the existing enum set) ────


class UserRole(str, Enum):
    """Standard platform roles for seed data."""

    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    VIEWER = "viewer"
    AUDITOR = "auditor"
    SYSTEM = "system"


class PermissionName(str, Enum):
    """Granular permission identifiers for seed data (25 permissions)."""

    # User management
    CREATE_USER = "create_user"
    READ_USER = "read_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    USER_MANAGEMENT = "user_management"

    # Role management
    CREATE_ROLE = "create_role"
    READ_ROLE = "read_role"
    UPDATE_ROLE = "update_role"
    DELETE_ROLE = "delete_role"
    MANAGE_ROLES = "manage_roles"

    # Document management
    CREATE_DOCUMENT = "create_document"
    READ_DOCUMENT = "read_document"
    UPDATE_DOCUMENT = "update_document"
    DELETE_DOCUMENT = "delete_document"
    VIEW_DOCUMENTS = "view_documents"
    MANAGE_DOCUMENTS = "manage_documents"

    # Session management
    CREATE_SESSION = "create_session"
    READ_SESSION = "read_session"
    UPDATE_SESSION = "update_session"
    DELETE_SESSION = "delete_session"
    VIEW_SESSIONS = "view_sessions"

    # Audit & Reporting & Operations
    VIEW_AUDIT_LOGS = "view_audit_logs"
    CREATE_REPORTS = "create_reports"
    EXPORT_DATA = "export_data"
    SYSTEM_OPERATIONS = "system_operations"


# ─── Descriptions ───────────────────────────────────────────────────────

ROLE_DESCRIPTIONS: dict[UserRole, str] = {
    UserRole.ADMIN: "Full platform administrator with unrestricted access",
    UserRole.MANAGER: "Manages users, audit logs, sessions and documents",
    UserRole.ANALYST: "Analyses data, manages documents and generates reports",
    UserRole.VIEWER: "Read-only access to documents and reports",
    UserRole.AUDITOR: "Read-only compliance and audit log monitoring",
    UserRole.SYSTEM: "Service account for automated system operations",
}

PERMISSION_DESCRIPTIONS: dict[PermissionName, str] = {
    PermissionName.CREATE_USER: "Create new user accounts",
    PermissionName.READ_USER: "View user account details",
    PermissionName.UPDATE_USER: "Update user account information",
    PermissionName.DELETE_USER: "Remove user accounts",
    PermissionName.USER_MANAGEMENT: "Full administration of user accounts",
    PermissionName.CREATE_ROLE: "Define new custom roles",
    PermissionName.READ_ROLE: "View role details and permissions",
    PermissionName.UPDATE_ROLE: "Modify role assignments and properties",
    PermissionName.DELETE_ROLE: "Remove obsolete roles",
    PermissionName.MANAGE_ROLES: "Manage role hierarchy and assignments",
    PermissionName.CREATE_DOCUMENT: "Upload and index new documents",
    PermissionName.READ_DOCUMENT: "Retrieve and read documents",
    PermissionName.UPDATE_DOCUMENT: "Edit document metadata and contents",
    PermissionName.DELETE_DOCUMENT: "Delete documents from repository",
    PermissionName.VIEW_DOCUMENTS: "Browse platform document catalog",
    PermissionName.MANAGE_DOCUMENTS: "Manage documents and indexing lifecycle",
    PermissionName.CREATE_SESSION: "Initiate new research and work sessions",
    PermissionName.READ_SESSION: "View research session details and progress",
    PermissionName.UPDATE_SESSION: "Modify session context and status",
    PermissionName.DELETE_SESSION: "Terminate and delete sessions",
    PermissionName.VIEW_SESSIONS: "View active and historical user sessions",
    PermissionName.VIEW_AUDIT_LOGS: "View the platform audit trail",
    PermissionName.CREATE_REPORTS: "Generate analytical reports",
    PermissionName.EXPORT_DATA: "Export platform data to external formats",
    PermissionName.SYSTEM_OPERATIONS: "Perform automated system maintenance",
}

# Role → set of permissions
DEFAULT_ROLE_PERMISSIONS: dict[UserRole, set[PermissionName]] = {
    UserRole.ADMIN: set(PermissionName),
    UserRole.MANAGER: {
        PermissionName.USER_MANAGEMENT,
        PermissionName.VIEW_AUDIT_LOGS,
        PermissionName.VIEW_SESSIONS,
        PermissionName.VIEW_DOCUMENTS,
        PermissionName.MANAGE_DOCUMENTS,
        PermissionName.CREATE_REPORTS,
        PermissionName.EXPORT_DATA,
    },
    UserRole.ANALYST: {
        PermissionName.VIEW_DOCUMENTS,
        PermissionName.READ_DOCUMENT,
        PermissionName.CREATE_DOCUMENT,
        PermissionName.MANAGE_DOCUMENTS,
        PermissionName.CREATE_SESSION,
        PermissionName.READ_SESSION,
        PermissionName.CREATE_REPORTS,
        PermissionName.EXPORT_DATA,
    },
    UserRole.VIEWER: {
        PermissionName.VIEW_DOCUMENTS,
        PermissionName.READ_DOCUMENT,
        PermissionName.CREATE_REPORTS,
    },
    UserRole.AUDITOR: {
        PermissionName.VIEW_AUDIT_LOGS,
        PermissionName.VIEW_SESSIONS,
        PermissionName.VIEW_DOCUMENTS,
        PermissionName.READ_DOCUMENT,
        PermissionName.EXPORT_DATA,
    },
    UserRole.SYSTEM: {
        PermissionName.VIEW_DOCUMENTS,
        PermissionName.CREATE_REPORTS,
        PermissionName.EXPORT_DATA,
        PermissionName.SYSTEM_OPERATIONS,
    },
}


# ─── Public seed functions ─────────────────────────────────────────────


def seed_roles(session: object) -> None:  # SQLAlchemy Session
    """Create a ``Role`` entity for every ``UserRole`` enum value.

    Existing roles (matched by *name*) are skipped so the call is
    idempotent.
    """
    for role_enum in UserRole:
        existing = session.execute(
            select(Role).where(Role.name == role_enum.value)
        ).scalar_one_or_none()

        if existing is not None:
            logger.debug("Role %s already exists – skipping", role_enum.value)
            continue

        session.add(
            Role(
                name=role_enum.value,
                description=ROLE_DESCRIPTIONS[role_enum],
            )
        )
        logger.info("Seeded role: %s", role_enum.value)


def seed_permissions(session: object) -> None:  # SQLAlchemy Session
    """Create a ``Permission`` entity for every ``PermissionName`` value.

    Existing permissions are skipped for idempotency.
    """
    for perm_enum in PermissionName:
        existing = session.execute(
            select(Permission).where(Permission.name == perm_enum.value)
        ).scalar_one_or_none()

        if existing is not None:
            logger.debug("Permission %s already exists – skipping", perm_enum.value)
            continue

        session.add(
            Permission(
                name=perm_enum.value,
                description=PERMISSION_DESCRIPTIONS[perm_enum],
            )
        )
        logger.info("Seeded permission: %s", perm_enum.value)


def assign_default_permissions(session: object) -> None:  # SQLAlchemy Session
    """Link every seeded role to its default permissions.

    Only missing rows in the ``role_permission`` association table
    are inserted, so repeated calls are safe.
    """
    for role_enum, perm_set in DEFAULT_ROLE_PERMISSIONS.items():
        role = session.execute(
            select(Role).where(Role.name == role_enum.value)
        ).scalar_one_or_none()

        if role is None:
            logger.warning(
                "Role %s not found – cannot assign permissions",
                role_enum.value,
            )
            continue

        for perm_enum in perm_set:
            perm = session.execute(
                select(Permission).where(Permission.name == perm_enum.value)
            ).scalar_one_or_none()

            if perm is None:
                logger.warning(
                    "Permission %s not found – skipping assignment to role %s",
                    perm_enum.value,
                    role_enum.value,
                )
                continue

            # Check for an existing association row
            assoc = session.execute(
                select(role_permission.c.role_id).where(
                    role_permission.c.role_id == role.id,
                    role_permission.c.permission_id == perm.id,
                )
            ).scalar_one_or_none()

            if assoc is not None:
                logger.debug(
                    "Permission %s already assigned to role %s – skipping",
                    perm_enum.value,
                    role_enum.value,
                )
                continue

            session.execute(
                insert(role_permission),
                [{"role_id": role.id, "permission_id": perm.id}],
            )
            logger.info(
                "Assigned permission %s to role %s",
                perm_enum.value,
                role_enum.value,
            )


def seed_admin_user(session: object) -> None:  # SQLAlchemy Session
    """Create or update the bootstrap admin user.

    Configuration is read from ``get_settings()`` with sensible
    defaults.  A warning is logged if the default password is still
    in use.
    """
    settings = get_settings()

    # Credentials – try settings first, then hard-coded defaults
    admin_username = (
        getattr(settings, "ADMIN_USERNAME", None)
        or getattr(settings, "admin_username", None)
        or "admin"
    )

    admin_email = (
        getattr(settings, "ADMIN_EMAIL", None)
        or getattr(settings, "admin_email", None)
        or "admin@lakenterprises.com"
    )

    admin_password = (
        getattr(settings, "ADMIN_PASSWORD", None)
        or getattr(settings, "admin_password", None)
        or "Admin123!"
    )

    default_password = "Admin123!"

    if admin_password == default_password:
        logger.warning(
            "The admin user is using the default password. "
            "Change it immediately in production."
        )

    # Look up existing user by email
    user = session.execute(
        select(User).where(User.email == admin_email)
    ).scalar_one_or_none()

    salt_hex = hashlib.sha256(os.urandom(32)).hexdigest()
    key = hashlib.pbkdf2_hmac(
        "sha256", admin_password.encode(), bytes.fromhex(salt_hex), 100_000
    )
    hashed = salt_hex + key.hex()

    if user is None:
        user = User(
            username=admin_username,
            email=admin_email,
            password_hash=hashed,
            first_name="System",
            last_name="Administrator",
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        session.flush()  # populate user.id
        logger.info("Created admin user: %s", admin_email)
    else:
        # Update stale fields (idempotent)
        user.username = admin_username
        user.first_name = "System"
        user.last_name = "Administrator"
        user.is_active = True
        user.password_hash = hashed
        logger.info("Updated admin user: %s", admin_email)

    # Assign admin role
    role = session.execute(
        select(Role).where(Role.name == UserRole.ADMIN.value)
    ).scalar_one_or_none()

    if role is None:
        logger.warning("Admin role not found – cannot assign to admin user")
        return

    # Ensure the user-role association exists
    assoc = session.execute(
        select(role_user.c.user_id).where(
            role_user.c.user_id == user.id,
            role_user.c.role_id == role.id,
        )
    ).scalar_one_or_none()

    if assoc is None:
        session.execute(
            insert(role_user),
            [{"user_id": user.id, "role_id": role.id}],
        )
        logger.info("Assigned admin role to user %s", admin_email)


# ─── Master entry point ────────────────────────────────────────────────


def seed_all() -> None:
    """Initialise the database and load all seed data.

    1. Creates tables (``init_db``) if they do not exist.
    2. Seeds roles, permissions, role-permission assignments and
       the admin user within a **single transaction**.
    3. Rolls back on any error so partial data is never committed.
    """
    init_db()
    session = get_db_session()

    try:
        seed_roles(session)
        seed_permissions(session)
        assign_default_permissions(session)
        seed_admin_user(session)
        session.commit()
        logger.info("All seed data committed successfully.")
    except Exception:
        session.rollback()
        logger.exception("Seed failed – transaction rolled back.")
        raise


__all__ = [
    "assign_default_permissions",
    "seed_all",
    "seed_admin_user",
    "seed_permissions",
    "seed_roles",
]
