"""Long-term process and entity memory store backed by relational persistence."""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from lakenterprises.db import get_db_session
from lakenterprises.memory.models import LongTermMemoryItem, MemoryType
from lakenterprises.models.entities import ProcessMemory
from lakenterprises.repositories import ProcessMemoryRepository

logger = logging.getLogger(__name__)


class LongTermProcessMemoryStore:
    """Manages persistent, cross-process enterprise memories in the relational database."""

    def __init__(self, session_factory=None) -> None:
        self._session_factory = session_factory or get_db_session

    def _entity_to_model(self, entity: ProcessMemory) -> LongTermMemoryItem:
        mem_type = MemoryType.FACT
        try:
            mem_type = MemoryType(entity.memory_type)
        except ValueError:
            pass

        return LongTermMemoryItem(
            id=entity.id,
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
            memory_type=mem_type,
            key=entity.key,
            content=entity.content,
            importance=entity.importance,
            metadata=entity.metadata_ or {},
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def store(
        self,
        item: LongTermMemoryItem,
        session: Optional[Session] = None,
    ) -> LongTermMemoryItem:
        """Store or update a durable enterprise memory item."""
        close_session = False
        db = session
        if db is None:
            db = self._session_factory()
            close_session = True

        try:
            repo = ProcessMemoryRepository(db)
            entity = repo.upsert(
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                key=item.key,
                content=item.content,
                memory_type=(
                    item.memory_type.value
                    if isinstance(item.memory_type, MemoryType)
                    else str(item.memory_type)
                ),
                metadata=item.metadata,
                importance=item.importance,
            )
            db.commit()
            return self._entity_to_model(entity)
        except Exception:
            db.rollback()
            raise
        finally:
            if close_session:
                db.close()

    def store_batch(
        self,
        items: List[LongTermMemoryItem],
        session: Optional[Session] = None,
    ) -> List[LongTermMemoryItem]:
        """Store multiple durable memory items in a single transaction."""
        if not items:
            return []

        close_session = False
        db = session
        if db is None:
            db = self._session_factory()
            close_session = True

        try:
            repo = ProcessMemoryRepository(db)
            saved: List[LongTermMemoryItem] = []
            for item in items:
                entity = repo.upsert(
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                    key=item.key,
                    content=item.content,
                    memory_type=(
                        item.memory_type.value
                        if isinstance(item.memory_type, MemoryType)
                        else str(item.memory_type)
                    ),
                    metadata=item.metadata,
                    importance=item.importance,
                )
                saved.append(self._entity_to_model(entity))
            db.commit()
            return saved
        except Exception:
            db.rollback()
            raise
        finally:
            if close_session:
                db.close()

    def get_by_id(
        self,
        memory_id: str,
        session: Optional[Session] = None,
    ) -> Optional[LongTermMemoryItem]:
        """Fetch a specific memory item by its ID."""
        close_session = False
        db = session
        if db is None:
            db = self._session_factory()
            close_session = True

        try:
            repo = ProcessMemoryRepository(db)
            entity = repo.get_by_id(memory_id)
            if not entity:
                return None
            return self._entity_to_model(entity)
        finally:
            if close_session:
                db.close()

    def get_by_key(
        self,
        entity_type: str,
        entity_id: str,
        key: str,
        session: Optional[Session] = None,
    ) -> Optional[LongTermMemoryItem]:
        """Fetch a memory item by entity type, entity ID, and topic key."""
        close_session = False
        db = session
        if db is None:
            db = self._session_factory()
            close_session = True

        try:
            repo = ProcessMemoryRepository(db)
            entity = repo.get_by_key(entity_type, entity_id, key)
            if not entity:
                return None
            return self._entity_to_model(entity)
        finally:
            if close_session:
                db.close()

    def query(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        min_importance: float = 0.0,
        limit: int = 50,
        offset: int = 0,
        session: Optional[Session] = None,
    ) -> List[LongTermMemoryItem]:
        """Query durable memory items by entity and attributes."""
        close_session = False
        db = session
        if db is None:
            db = self._session_factory()
            close_session = True

        try:
            repo = ProcessMemoryRepository(db)
            if entity_type and entity_id:
                entities = repo.get_by_entity(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    memory_type=memory_type,
                    min_importance=min_importance,
                    limit=limit,
                    offset=offset,
                )
            else:
                entities = repo.search(
                    query="",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    memory_type=memory_type,
                    min_importance=min_importance,
                    limit=limit,
                )
            return [self._entity_to_model(e) for e in entities]
        finally:
            if close_session:
                db.close()

    def search(
        self,
        query_text: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        min_importance: float = 0.0,
        limit: int = 20,
        session: Optional[Session] = None,
    ) -> List[LongTermMemoryItem]:
        """Search memory content and keys for query keywords."""
        close_session = False
        db = session
        if db is None:
            db = self._session_factory()
            close_session = True

        try:
            repo = ProcessMemoryRepository(db)
            entities = repo.search(
                query=query_text,
                entity_type=entity_type,
                entity_id=entity_id,
                memory_type=memory_type,
                min_importance=min_importance,
                limit=limit,
            )
            return [self._entity_to_model(e) for e in entities]
        finally:
            if close_session:
                db.close()

    def delete(
        self,
        memory_id: str,
        session: Optional[Session] = None,
    ) -> bool:
        """Delete a memory item by ID."""
        close_session = False
        db = session
        if db is None:
            db = self._session_factory()
            close_session = True

        try:
            repo = ProcessMemoryRepository(db)
            deleted = repo.delete(memory_id)
            if deleted:
                db.commit()
            return deleted
        except Exception:
            db.rollback()
            raise
        finally:
            if close_session:
                db.close()

    def delete_by_entity(
        self,
        entity_type: str,
        entity_id: str,
        session: Optional[Session] = None,
    ) -> int:
        """Delete all memories associated with a given entity."""
        close_session = False
        db = session
        if db is None:
            db = self._session_factory()
            close_session = True

        try:
            repo = ProcessMemoryRepository(db)
            count = repo.delete_by_entity(entity_type, entity_id)
            db.commit()
            return count
        except Exception:
            db.rollback()
            raise
        finally:
            if close_session:
                db.close()


default_long_term_store = LongTermProcessMemoryStore()
