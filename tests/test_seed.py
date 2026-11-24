"""Tests for the seed data loader (src/lakenterprises/seed.py)."""

import hashlib
import os
import tempfile

import pytest

# --- temp SQLite DB setup ---

_DB_PATH = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from sqlalchemy import select

from lakenterprises.db import get_db_session, init_db, reset_db
from lakenterprises.models.entities import Permission, Role, User
from lakenterprises.seed import (seed_admin_user, seed_all, seed_permissions,
                                 seed_roles)

# --- helpers ---


def _admin_user_hash(password: str) -> str:
    """Re-derive the admin password hash to verify against the stored value."""
    salt = hashlib.sha256(os.urandom(32)).hexdigest().encode()
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return (salt + key).hex()


# --- tests ---


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset to an empty DB before every test."""
    reset_db()
    yield


def test_seed_all_creates_correct_counts():
    seed_all()
    session = get_db_session()
    roles = session.execute(select(Role)).scalars().all()
    perms = session.execute(select(Permission)).scalars().all()
    users = session.execute(select(User)).scalars().all()
    assert len(roles) == 6, f"Expected 6 roles, got {len(roles)}"
    assert len(perms) == 25, f"Expected 25 permissions, got {len(perms)}"
    assert len(users) == 1, f"Expected 1 user, got {len(users)}"


def test_admin_user_exists_with_correct_details():
    seed_all()
    session = get_db_session()
    user = session.execute(select(User).where(User.username == "admin")).scalar_one()
    assert user.username == "admin"
    assert user.email == "admin@lakenterprises.com"
    assert user.first_name == "System"
    assert user.last_name == "Administrator"


def test_admin_password_verifies():
    seed_all()
    session = get_db_session()
    user = session.execute(
        select(User).where(User.email == "admin@lakenterprises.com")
    ).scalar_one()
    assert user.password_hash is not None
    stored = user.password_hash
    # The stored hash is: (salt_hex + key).hex()  ->  salt_hex + key_hex
    salt_hex = stored[:64]
    key_hex = stored[64:]
    key = bytes.fromhex(key_hex)
    expected = hashlib.pbkdf2_hmac(
        "sha256", "Admin123!".encode(), bytes.fromhex(salt_hex), 100_000
    )
    assert key == expected


def test_admin_user_has_admin_role():
    seed_all()
    session = get_db_session()
    user = session.execute(select(User).where(User.username == "admin")).scalar_one()
    role_names = [r.name for r in user.roles]
    assert "admin" in role_names, f"Admin role not assigned; got {role_names}"


def test_all_six_role_names_exist():
    seed_all()
    session = get_db_session()
    role_names = {r.name for r in session.execute(select(Role)).scalars().all()}
    expected = {"admin", "manager", "analyst", "viewer", "auditor", "system"}
    assert role_names == expected, f"Roles mismatch: got {role_names}"


def test_seed_all_is_idempotent():
    """Running seed_all twice should not raise (existing_data_ok)."""
    seed_all()
    seed_all()  # should not raise
    session = get_db_session()
    users = session.execute(select(User)).scalars().all()
    assert len(users) == 1, "Idempotent seed should not duplicate users"


def test_reset_db_then_seed_all():
    """reset_db followed by seed_all works cleanly."""
    reset_db()
    seed_all()
    session = get_db_session()
    roles = session.execute(select(Role)).scalars().all()
    perms = session.execute(select(Permission)).scalars().all()
    users = session.execute(select(User)).scalars().all()
    assert len(roles) == 6
    assert len(perms) == 25
    assert len(users) == 1
