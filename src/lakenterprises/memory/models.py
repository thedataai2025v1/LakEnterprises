"""Pydantic data models for short-term and long-term enterprise memory."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class MessageRole(str, Enum):
    """Role associated with a conversational turn."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class MemoryType(str, Enum):
    """Semantic classification for long-term memory items."""

    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    SUMMARY = "summary"
    LEARNING = "learning"


class ChatMessage(BaseModel):
    """Single message in a conversational session."""

    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=_now_utc)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionContext(BaseModel):
    """Active conversational session context."""

    session_id: str
    user_id: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    ttl_seconds: int = 86400


class LongTermMemoryItem(BaseModel):
    """Durable memory item stored across enterprise processes."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_type: str  # e.g., 'customer', 'vendor', 'process', 'incident'
    entity_id: str  # e.g., 'CUST-1001', 'PROC-404'
    memory_type: MemoryType = MemoryType.FACT
    key: str  # specific topic or attribute key
    content: str
    importance: float = Field(default=1.0, ge=0.0, le=5.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RecallRequest(BaseModel):
    """Request payload to recall relevant context for an agent prompt."""

    session_id: Optional[str] = None
    query: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    max_session_messages: int = 10
    max_long_term_items: int = 5
    min_importance: float = 0.0


class RecallResponse(BaseModel):
    """Synthesized context returned from the memory recall service."""

    session_id: Optional[str] = None
    recent_messages: List[ChatMessage] = Field(default_factory=list)
    long_term_memories: List[LongTermMemoryItem] = Field(default_factory=list)
    synthesized_context: str = ""


class WriteBackRequest(BaseModel):
    """Request to safely write back session turns and durable facts."""

    session_id: Optional[str] = None
    user_id: Optional[str] = None
    messages_to_append: List[ChatMessage] = Field(default_factory=list)
    long_term_items_to_store: List[LongTermMemoryItem] = Field(default_factory=list)
    session_variables: Dict[str, Any] = Field(default_factory=dict)
    scrub_secrets: bool = True


class WriteBackResponse(BaseModel):
    """Result of memory write-back operation."""

    success: bool
    session_id: Optional[str] = None
    messages_added: int = 0
    long_term_items_saved: int = 0
    scrubbed: bool = True
    redacted_items_count: int = 0
