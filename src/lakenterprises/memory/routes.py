"""FastAPI router endpoints for enterprise session and process memory."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from lakenterprises.memory.long_term_store import default_long_term_store
from lakenterprises.memory.models import (
    ChatMessage,
    LongTermMemoryItem,
    RecallRequest,
    RecallResponse,
    SessionContext,
    WriteBackRequest,
    WriteBackResponse,
)
from lakenterprises.memory.service import default_memory_service
from lakenterprises.memory.session_store import default_session_store

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


# ── Short-Term Session Store Endpoints ─────────────────────────────────


@router.post(
    "/sessions/{session_id}/messages",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Append a message turn to the session",
)
def append_message(
    session_id: str,
    message: ChatMessage,
    ttl: Optional[int] = Query(None, description="Optional TTL override in seconds"),
) -> Dict[str, Any]:
    default_session_store.append_message(session_id, message, ttl=ttl)
    return {"status": "ok", "session_id": session_id}


@router.get(
    "/sessions/{session_id}",
    response_model=SessionContext,
    summary="Retrieve session history and context",
)
def get_session(session_id: str) -> SessionContext:
    return default_session_store.get_session(session_id)


@router.delete(
    "/sessions/{session_id}",
    response_model=Dict[str, Any],
    summary="Clear session memory",
)
def clear_session(session_id: str) -> Dict[str, Any]:
    cleared = default_session_store.clear_session(session_id)
    return {"status": "cleared" if cleared else "not_found", "session_id": session_id}


@router.post(
    "/sessions/{session_id}/variables",
    response_model=Dict[str, Any],
    summary="Set working memory variables for session",
)
def set_variables(
    session_id: str,
    variables: Dict[str, Any],
    ttl: Optional[int] = Query(None, description="Optional TTL in seconds"),
) -> Dict[str, Any]:
    default_session_store.set_variables(session_id, variables, ttl=ttl)
    return {"status": "ok", "session_id": session_id, "keys": list(variables.keys())}


@router.get(
    "/sessions/{session_id}/variables",
    response_model=Dict[str, Any],
    summary="Get all session variables",
)
def get_variables(session_id: str) -> Dict[str, Any]:
    return default_session_store.get_all_variables(session_id)


# ── Long-Term Process Memory Endpoints ──────────────────────────────────


@router.post(
    "/long-term",
    response_model=LongTermMemoryItem,
    status_code=status.HTTP_201_CREATED,
    summary="Store a durable enterprise memory item",
)
def store_long_term_memory(item: LongTermMemoryItem) -> LongTermMemoryItem:
    return default_long_term_store.store(item)


@router.get(
    "/long-term",
    response_model=List[LongTermMemoryItem],
    summary="Query or search durable enterprise memories",
)
def query_long_term_memory(
    entity_type: Optional[str] = Query(
        None, description="Filter by entity type (e.g. customer, process)"
    ),
    entity_id: Optional[str] = Query(
        None, description="Filter by entity ID (e.g. CUST-1001)"
    ),
    memory_type: Optional[str] = Query(
        None, description="Filter by memory type (fact, preference, etc.)"
    ),
    query: Optional[str] = Query(None, description="Search query string"),
    min_importance: float = Query(0.0, description="Minimum importance threshold"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[LongTermMemoryItem]:
    if query:
        return default_long_term_store.search(
            query_text=query,
            entity_type=entity_type,
            entity_id=entity_id,
            memory_type=memory_type,
            min_importance=min_importance,
            limit=limit,
        )
    return default_long_term_store.query(
        entity_type=entity_type,
        entity_id=entity_id,
        memory_type=memory_type,
        min_importance=min_importance,
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/long-term/{memory_id}",
    response_model=Dict[str, Any],
    summary="Delete a long-term memory item",
)
def delete_long_term_memory(memory_id: str) -> Dict[str, Any]:
    deleted = default_long_term_store.delete(memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory item '{memory_id}' not found.",
        )
    return {"status": "deleted", "id": memory_id}


# ── Recall & Write-Back Endpoints ─────────────────────────────────────


@router.post(
    "/recall",
    response_model=RecallResponse,
    summary="Recall conversational and factual context for agent prompt",
)
def recall_memory(request: RecallRequest) -> RecallResponse:
    return default_memory_service.recall(request)


@router.post(
    "/write-back",
    response_model=WriteBackResponse,
    summary="Safely write back conversation turns and facts with PII scrubbing",
)
def write_back_memory(request: WriteBackRequest) -> WriteBackResponse:
    return default_memory_service.write_back(request)
