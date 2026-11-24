"""FastAPI routes for Document Ingestion, Management, and Hybrid Search.

Implements role-based access control:
- Ingestion: requires 'analyst' or 'admin'
- Listing, viewing, and search: requires 'viewer', 'analyst', or 'admin'
- Deletion: requires 'admin' (approval/destructive gate)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from lakenterprises.auth.middleware import get_current_user, require_role
from lakenterprises.db import get_db_session
from lakenterprises.models.entities import User
from lakenterprises.services.document import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class DocumentIngestRequest(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=255, description="Document title/identifier"
    )
    content: str = Field(..., min_length=1, description="Raw text or markdown content")
    source_url: Optional[str] = Field(
        None, max_length=500, description="Source URL or file path"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default_factory=dict, description="Custom metadata"
    )
    chunk_size: int = Field(
        500, ge=50, le=5000, description="Target character count per chunk"
    )
    chunk_overlap: int = Field(
        50, ge=0, le=1000, description="Character overlap between chunks"
    )


class ChunkSummary(BaseModel):
    chunk_id: str
    chunk_index: int
    content: str
    word_count: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None


class DocumentResponse(BaseModel):
    id: str
    name: str
    source_url: Optional[str] = None
    created_at: str
    chunk_count: int
    chunks: Optional[list[ChunkSummary]] = None
    metadata: Optional[dict[str, Any]] = None


class DocumentListItem(BaseModel):
    id: str
    name: str
    source_url: Optional[str] = None
    created_at: str
    metadata: Optional[dict[str, Any]] = None


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string")
    top_k: int = Field(5, ge=1, le=50, description="Maximum number of chunks to return")


class SearchResultItem(BaseModel):
    text: str
    score: float
    source: Optional[str] = None
    strategy: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class DocumentSearchResponse(BaseModel):
    query: str
    total_results: int
    results: list[SearchResultItem]


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def get_document_service() -> DocumentService:
    session = get_db_session()
    return DocumentService(db_session=session)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/ingest",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest and chunk a document",
    dependencies=[Depends(require_role("analyst"))],
)
def ingest_document(
    body: DocumentIngestRequest,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Ingest a document, split into chunks, save to database, and index in vector store."""
    try:
        doc, chunks = service.ingest_text(
            name=body.name,
            content=body.content,
            source_url=body.source_url,
            metadata=body.metadata,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap,
        )
    except Exception as exc:
        logger.error("Document ingestion error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to ingest document: {exc}",
        )

    chunk_summaries = [
        ChunkSummary(
            chunk_id=c.chunk_id,
            chunk_index=c.chunk_index,
            content=c.content or "",
            word_count=c.word_count,
            metadata=c.metadata_,
        )
        for c in chunks
    ]

    return DocumentResponse(
        id=doc.id,
        name=doc.name,
        source_url=doc.source_url,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
        chunk_count=len(chunks),
        chunks=chunk_summaries,
        metadata=doc.metadata_,
    )


@router.get(
    "",
    response_model=list[DocumentListItem],
    summary="List all ingested documents",
    dependencies=[Depends(require_role("viewer"))],
)
def list_documents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> list[DocumentListItem]:
    """Retrieve paginated list of ingested documents."""
    docs = service.list_documents(limit=limit, offset=offset)
    return [
        DocumentListItem(
            id=d.id,
            name=d.name,
            source_url=d.source_url,
            created_at=d.created_at.isoformat() if d.created_at else "",
            metadata=d.metadata_,
        )
        for d in docs
    ]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details and chunks",
    dependencies=[Depends(require_role("viewer"))],
)
def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Retrieve a document and all of its chunks by ID."""
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )

    chunks = service.get_document_chunks(document_id)
    chunk_summaries = [
        ChunkSummary(
            chunk_id=c.chunk_id,
            chunk_index=c.chunk_index,
            content=c.content or "",
            word_count=c.word_count,
            metadata=c.metadata_,
        )
        for c in chunks
    ]

    return DocumentResponse(
        id=doc.id,
        name=doc.name,
        source_url=doc.source_url,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
        chunk_count=len(chunks),
        chunks=chunk_summaries,
        metadata=doc.metadata_,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a document and its chunks",
    dependencies=[Depends(require_role("admin"))],
)
def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """Delete a document and all its chunks (Admin only)."""
    deleted = service.delete_document(document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )
    return {
        "message": f"Document '{document_id}' and all associated chunks deleted successfully"
    }


@router.post(
    "/search",
    response_model=DocumentSearchResponse,
    summary="Search documents using hybrid retrieval",
    dependencies=[Depends(require_role("viewer"))],
)
def search_documents(
    body: DocumentSearchRequest,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentSearchResponse:
    """Execute hybrid search (BM25 keyword + semantic vector search with RRF)."""
    results = service.search(query=body.query, top_k=body.top_k)
    items = [
        SearchResultItem(
            text=r.get("text", ""),
            score=round(float(r.get("score", 0.0)), 4),
            source=r.get("source"),
            strategy=r.get("strategy"),
            metadata=r.get("metadata"),
        )
        for r in results
    ]
    return DocumentSearchResponse(
        query=body.query,
        total_results=len(items),
        results=items,
    )
