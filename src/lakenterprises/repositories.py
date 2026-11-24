"""Data-access layer for the LakEnterprises platform.

Each repository class owns one entity and exposes CRUD / query helpers
against a SQLAlchemy ``Session``.  Methods return ``None`` (never raise)
when a row is not found and return lists for collection queries.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from lakenterprises.models.entities import (AuditLog, AuthToken, Document,
                                            DocumentChunk, Permission, Role,
                                            User)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserRepository:
    """Repository for the :class:`User` entity."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_active: bool = True,
        is_verified: bool = False,
        roles: Optional[List[Role]] = None,
    ) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
            is_verified=is_verified,
        )
        if roles:
            user.roles.extend(roles)
        self.db.add(user)
        self.db.flush()
        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

    def get_all(self) -> List[User]:
        return (
            self.db.execute(select(User).order_by(User.created_at.desc()))
            .scalars()
            .all()
        )

    def get_active(self) -> List[User]:
        return (
            self.db.execute(
                select(User)
                .where(User.is_active.is_(True))
                .order_by(User.created_at.desc())
            )
            .scalars()
            .all()
        )

    def search(self, query: str) -> List[User]:
        stmt = select(User).where(
            or_(
                User.username.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%"),
                User.first_name.ilike(f"%{query}%"),
                User.last_name.ilike(f"%{query}%"),
            )
        )
        return self.db.execute(stmt).scalars().all()

    def update(
        self,
        user_id: str,
        *,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
    ) -> Optional[User]:
        user = self.db.get(User, user_id)
        if user is None:
            return None
        if email is not None:
            user.email = email
        if password_hash is not None:
            user.password_hash = password_hash
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if is_active is not None:
            user.is_active = is_active
        if is_verified is not None:
            user.is_verified = is_verified
        self.db.flush()
        return user

    def delete(self, user_id: str) -> bool:
        user = self.db.get(User, user_id)
        if user is None:
            return False
        self.db.delete(user)
        self.db.flush()
        return True

    def assign_role(self, user_id: str, role: Role) -> Optional[User]:
        user = self.get_by_id(user_id)
        if user and role not in user.roles:
            user.roles.append(role)
            self.db.flush()
        return user

    def get_by_role_name(self, role_name: str) -> List[User]:
        return (
            self.db.execute(
                select(User)
                .join(User.roles)
                .where(Role.name == role_name)
                .order_by(User.created_at.desc())
            )
            .scalars()
            .all()
        )


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------


class RoleRepository:
    """Repository for the :class:`Role` entity."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[List[Permission]] = None,
    ) -> Role:
        role = Role(name=name, description=description)
        if permissions:
            role.permissions.extend(permissions)
        self.db.add(role)
        self.db.flush()
        return role

    def get_by_id(self, role_id: str) -> Optional[Role]:
        return self.db.get(Role, role_id)

    def get_by_name(self, name: str) -> Optional[Role]:
        return self.db.execute(
            select(Role).where(Role.name == name)
        ).scalar_one_or_none()

    def get_all(self) -> List[Role]:
        return self.db.execute(select(Role).order_by(Role.name)).scalars().all()

    def update(
        self,
        role_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Role]:
        role = self.db.get(Role, role_id)
        if role is None:
            return None
        if name is not None:
            role.name = name
        if description is not None:
            role.description = description
        self.db.flush()
        return role

    def delete(self, role_id: str) -> bool:
        role = self.db.get(Role, role_id)
        if role is None:
            return False
        self.db.delete(role)
        self.db.flush()
        return True

    def add_permission(self, role_id: str, permission: Permission) -> Optional[Role]:
        role = self.db.get(Role, role_id)
        if role is None:
            return None
        if permission not in role.permissions:
            role.permissions.append(permission)
            self.db.flush()
        return role

    def remove_permission(self, role_id: str, permission: Permission) -> Optional[Role]:
        role = self.db.get(Role, role_id)
        if role is None:
            return None
        if permission in role.permissions:
            role.permissions.remove(permission)
            self.db.flush()
        return role


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------


class PermissionRepository:
    """Repository for the :class:`Permission` entity."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        module: Optional[str] = None,
    ) -> Permission:
        perm = Permission(name=name, description=description, module=module)
        self.db.add(perm)
        self.db.flush()
        return perm

    def get_by_id(self, perm_id: str) -> Optional[Permission]:
        return self.db.get(Permission, perm_id)

    def get_by_name(self, name: str) -> Optional[Permission]:
        return self.db.execute(
            select(Permission).where(Permission.name == name)
        ).scalar_one_or_none()

    def get_all(self) -> List[Permission]:
        return (
            self.db.execute(select(Permission).order_by(Permission.name))
            .scalars()
            .all()
        )

    def update(
        self,
        perm_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        module: Optional[str] = None,
    ) -> Optional[Permission]:
        perm = self.db.get(Permission, perm_id)
        if perm is None:
            return None
        if name is not None:
            perm.name = name
        if description is not None:
            perm.description = description
        if module is not None:
            perm.module = module
        self.db.flush()
        return perm

    def delete(self, perm_id: str) -> bool:
        perm = self.db.get(Permission, perm_id)
        if perm is None:
            return False
        self.db.delete(perm)
        self.db.flush()
        return True


# ---------------------------------------------------------------------------
# AuthToken
# ---------------------------------------------------------------------------


class AuthTokenRepository:
    """Repository for the :class:`AuthToken` entity."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: str,
        token_hash: str,
        id: Optional[str] = None,
        refresh_token_hash: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuthToken:
        attrs = {
            "user_id": user_id,
            "token_hash": token_hash,
            "refresh_token_hash": refresh_token_hash,
            "expires_at": expires_at,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "is_revoked": False,
        }
        if id:
            attrs["id"] = id
        token = AuthToken(**attrs)
        self.db.add(token)
        self.db.flush()
        return token

    def get_all(self) -> List[AuthToken]:
        return (
            self.db.execute(select(AuthToken).order_by(AuthToken.created_at.desc()))
            .scalars()
            .all()
        )

    def get_by_id(self, token_id: str) -> Optional[AuthToken]:
        return self.db.get(AuthToken, token_id)

    def get_by_token(self, token_hash: str) -> Optional[AuthToken]:
        return self.db.execute(
            select(AuthToken).where(AuthToken.token_hash == token_hash)
        ).scalar_one_or_none()

    def revoke_by_id(self, token_id: str) -> bool:
        token = self.db.get(AuthToken, token_id)
        if token is None:
            return False
        token.is_revoked = True
        self.db.flush()
        return True

    def revoke_all_for_user(self, user_id: str) -> int:
        tokens = (
            self.db.execute(select(AuthToken).where(AuthToken.user_id == user_id))
            .scalars()
            .all()
        )
        count = 0
        for token in tokens:
            if not token.is_revoked:
                token.is_revoked = True
                count += 1
        self.db.flush()
        return count

    def get_valid_for_user(self, user_id: str) -> List[AuthToken]:
        now = datetime.now()
        stmt = (
            select(AuthToken)
            .where(
                AuthToken.user_id == user_id,
                AuthToken.is_revoked.is_(False),
                AuthToken.expires_at > now,
            )
            .order_by(AuthToken.expires_at.desc())
        )
        return self.db.execute(stmt).scalars().all()

    def cleanup_expired(self) -> int:
        now = datetime.now()
        expired = (
            self.db.execute(
                select(AuthToken).where(
                    AuthToken.expires_at <= now, AuthToken.is_revoked.is_(False)
                )
            )
            .scalars()
            .all()
        )
        count = 0
        for token in expired:
            token.is_revoked = True
            count += 1
        self.db.flush()
        return count


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class DocumentRepository:
    """Repository for the :class:`Document` entity."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        name: str,
        content: Optional[str] = None,
        source_url: Optional[str] = None,
        metadata: Optional[dict] = None,
        id: Optional[str] = None,
    ) -> Document:
        import uuid as _uuid

        doc_id = id or str(_uuid.uuid4())
        doc = Document(
            id=doc_id,
            name=name,
            content=content,
            source_url=source_url,
            metadata_=metadata,
        )
        self.db.add(doc)
        self.db.flush()
        return doc

    def get_by_id(self, document_id: str) -> Optional[Document]:
        return self.db.get(Document, document_id)

    def get_by_name(self, name: str) -> Optional[Document]:
        return self.db.execute(
            select(Document).where(Document.name == name)
        ).scalar_one_or_none()

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Document]:
        return (
            self.db.execute(
                select(Document)
                .order_by(Document.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )

    def update(
        self,
        document_id: str,
        *,
        name: Optional[str] = None,
        content: Optional[str] = None,
        source_url: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Document]:
        doc = self.db.get(Document, document_id)
        if doc is None:
            return None
        if name is not None:
            doc.name = name
        if content is not None:
            doc.content = content
        if source_url is not None:
            doc.source_url = source_url
        if metadata is not None:
            doc.metadata_ = metadata
        self.db.flush()
        return doc

    def delete(self, document_id: str) -> bool:
        doc = self.db.get(Document, document_id)
        if doc is None:
            return False
        self.db.delete(doc)
        self.db.flush()
        return True

    def count(self) -> int:
        return len(self.db.execute(select(Document.id)).scalars().all())


# ---------------------------------------------------------------------------
# DocumentChunk
# ---------------------------------------------------------------------------


class DocumentChunkRepository:
    """Repository for the :class:`DocumentChunk` entity."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        document_id: str,
        chunk_index: int,
        content: str,
        chunk_id: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[dict] = None,
        word_count: Optional[int] = None,
    ) -> DocumentChunk:
        import uuid as _uuid

        cid = chunk_id or str(_uuid.uuid4())
        wc = (
            word_count
            if word_count is not None
            else (len(content.split()) if content else 0)
        )
        chunk = DocumentChunk(
            chunk_id=cid,
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            text=content,
            embedding=embedding,
            metadata_=metadata,
            word_count=wc,
        )
        self.db.add(chunk)
        self.db.flush()
        return chunk

    def get_by_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        return self.db.get(DocumentChunk, chunk_id)

    def get_by_document_id(self, document_id: str) -> List[DocumentChunk]:
        return (
            self.db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
            .scalars()
            .all()
        )

    def get_all(self) -> List[DocumentChunk]:
        return (
            self.db.execute(
                select(DocumentChunk).order_by(DocumentChunk.created_at.desc())
            )
            .scalars()
            .all()
        )

    def update(
        self,
        chunk_id: str,
        *,
        content: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[dict] = None,
        word_count: Optional[int] = None,
    ) -> Optional[DocumentChunk]:
        chunk = self.db.get(DocumentChunk, chunk_id)
        if chunk is None:
            return None
        if content is not None:
            chunk.content = content
        if embedding is not None:
            chunk.embedding = embedding
        if metadata is not None:
            chunk.metadata = metadata
        if word_count is not None:
            chunk.word_count = word_count
        self.db.flush()
        return chunk

    def delete(self, chunk_id: str) -> bool:
        chunk = self.db.get(DocumentChunk, chunk_id)
        if chunk is None:
            return False
        self.db.delete(chunk)
        self.db.flush()
        return True

    def delete_by_document_id(self, document_id: str) -> int:
        chunks = self.get_by_document_id(document_id)
        count = 0
        for chunk in chunks:
            self.db.delete(chunk)
            count += 1
        self.db.flush()
        return count

    def search_by_keywords(self, keywords: str) -> List[DocumentChunk]:
        """Return chunks whose *content* contains all given space-separated keywords.

        This is a simple SQL ``LIKE`` search; for production workloads a
        vector-based or full-text index would be preferred.
        """
        if not keywords:
            return []
        terms = keywords.strip().split()
        if not terms:
            return []
        conditions = [DocumentChunk.content.ilike(f"%{term}%") for term in terms]
        stmt = select(DocumentChunk).where(
            or_(*conditions),
            DocumentChunk.content.isnot(None),
        )
        return (
            self.db.execute(stmt.order_by(DocumentChunk.created_at.desc()))
            .scalars()
            .all()
        )

    def search(self, query: str) -> List[DocumentChunk]:
        return self.search_by_keywords(query)


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class AuditLogRepository:
    """Repository for the :class:`AuditLog` entity."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        action: str,
        user_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        details: Optional[dict] = None,
        severity: str = "INFO",
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            severity=severity,
            ip_address=ip_address,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def get_by_id(self, entry_id: str) -> Optional[AuditLog]:
        return self.db.get(AuditLog, entry_id)

    def get_by_user_id(self, user_id: str) -> List[AuditLog]:
        return (
            self.db.execute(
                select(AuditLog)
                .where(AuditLog.user_id == user_id)
                .order_by(AuditLog.timestamp.desc())
            )
            .scalars()
            .all()
        )

    def get_by_action(self, action: str) -> List[AuditLog]:
        return (
            self.db.execute(
                select(AuditLog)
                .where(AuditLog.action == action)
                .order_by(AuditLog.timestamp.desc())
            )
            .scalars()
            .all()
        )

    def get_by_severity(self, severity: str) -> List[AuditLog]:
        return (
            self.db.execute(
                select(AuditLog)
                .where(AuditLog.severity == severity)
                .order_by(AuditLog.timestamp.desc())
            )
            .scalars()
            .all()
        )

    def get_by_entity(self, entity_type: str, entity_id: str) -> List[AuditLog]:
        return (
            self.db.execute(
                select(AuditLog)
                .where(
                    AuditLog.entity_type == entity_type,
                    AuditLog.entity_id == entity_id,
                )
                .order_by(AuditLog.timestamp.desc())
            )
            .scalars()
            .all()
        )

    def get_all(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditLog]:
        stmt = select(AuditLog)
        if start_date is not None:
            stmt = stmt.where(AuditLog.timestamp >= start_date)
        if end_date is not None:
            stmt = stmt.where(AuditLog.timestamp <= end_date)
        stmt = stmt.order_by(AuditLog.timestamp.desc())
        return self.db.execute(stmt).scalars().all()

    def get_recent(self, limit: int = 50) -> List[AuditLog]:
        return (
            self.db.execute(
                select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
            )
            .scalars()
            .all()
        )


# ---------------------------------------------------------------------------
# SessionRecord (uses AuthToken as the persistence layer)
# ---------------------------------------------------------------------------


class SessionRecordRepository:
    """Repository for session tracking via the :class:`AuthToken` entity.

    The platform does not have a dedicated ``SessionRecord`` table;
    sessions are represented as :class:`AuthToken` rows.  This
    repository adds higher-level helpers on top of the auth-token
    store.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: str,
        session_id: str,
        token_hash: str,
        refresh_token_hash: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuthToken:
        return self._token_repo().create(
            id=session_id,
            user_id=user_id,
            token_hash=token_hash,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def get_by_id(self, record_id: str) -> Optional[AuthToken]:
        return self.db.get(AuthToken, record_id)

    def get_by_session_id(self, session_id: str) -> Optional[AuthToken]:
        return self.db.execute(
            select(AuthToken).where(AuthToken.id == session_id)
        ).scalar_one_or_none()

    def get_active_for_user(self, user_id: str) -> List[AuthToken]:
        now = datetime.now()
        stmt = (
            select(AuthToken)
            .where(
                AuthToken.user_id == user_id,
                AuthToken.is_revoked.is_(False),
                AuthToken.expires_at > now,
            )
            .order_by(AuthToken.expires_at.desc())
        )
        return self.db.execute(stmt).scalars().all()

    def get_all_active(self) -> List[AuthToken]:
        now = datetime.now()
        stmt = (
            select(AuthToken)
            .where(AuthToken.is_revoked.is_(False), AuthToken.expires_at > now)
            .order_by(AuthToken.expires_at.desc())
        )
        return self.db.execute(stmt).scalars().all()

    def mark_expired_for_user(self, user_id: str) -> int:
        now = datetime.now()
        expired = (
            self.db.execute(
                select(AuthToken).where(
                    AuthToken.user_id == user_id, AuthToken.expires_at <= now
                )
            )
            .scalars()
            .all()
        )
        count = 0
        for token in expired:
            if not token.is_revoked:
                token.is_revoked = True
                count += 1
        self.db.flush()
        return count

    def cleanup_expired(self) -> int:
        return self._token_repo().cleanup_expired()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _token_repo(self) -> AuthTokenRepository:
        return AuthTokenRepository(self.db)


__all__ = [
    "AuditLogRepository",
    "AuthTokenRepository",
    "DocumentChunkRepository",
    "PermissionRepository",
    "RoleRepository",
    "SessionRecordRepository",
    "UserRepository",
]
