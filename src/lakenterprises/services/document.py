"""Document service orchestrating ingestion, chunking, storage, and retrieval."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from lakenterprises.db import get_db_session
from lakenterprises.document.chunker import TextChunker
from lakenterprises.document.vector_store import InMemoryVectorStore
from lakenterprises.models.entities import Document, DocumentChunk
from lakenterprises.repositories import (DocumentChunkRepository,
                                         DocumentRepository)
from lakenterprises.retriever import HybridRetriever

logger = logging.getLogger(__name__)

# Global singleton in-memory vector store for application lifecycle
_default_vector_store: Optional[InMemoryVectorStore] = None


def get_default_vector_store() -> InMemoryVectorStore:
    """Return the application singleton in-memory vector store."""
    global _default_vector_store
    if _default_vector_store is None:
        _default_vector_store = InMemoryVectorStore()
    return _default_vector_store


class DocumentService:
    """High-level document processing service.

    Handles ingestion, boundary-aware chunking, database persistence,
    vector embedding, and hybrid retrieval.
    """

    def __init__(
        self,
        db_session: Optional[Session] = None,
        vector_store: Optional[InMemoryVectorStore] = None,
    ) -> None:
        self._db = db_session
        self._vector_store = vector_store or get_default_vector_store()

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = get_db_session()
        return self._db

    def ingest_text(
        self,
        name: str,
        content: str,
        source_url: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> tuple[Document, list[DocumentChunk]]:
        """Ingest text content, chunk it, persist records to DB, and index into vector store."""
        doc_repo = DocumentRepository(self.db)
        chunk_repo = DocumentChunkRepository(self.db)

        # Check if a document with this name already exists; if so, update or replace
        existing = doc_repo.get_by_name(name)
        if existing:
            doc_id = existing.id
            doc_repo.update(
                doc_id, content=content, source_url=source_url, metadata=metadata
            )
            chunk_repo.delete_by_document_id(doc_id)
            self._vector_store.delete_by_document_id(doc_id)
            doc = doc_repo.get_by_id(doc_id)
        else:
            doc = doc_repo.create(
                name=name,
                content=content,
                source_url=source_url,
                metadata=metadata,
            )

        # Split content into chunks
        chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        base_meta = dict(metadata or {})
        base_meta["document_id"] = doc.id
        base_meta["document_name"] = doc.name
        if source_url:
            base_meta["source_url"] = source_url

        chunks = chunker.split_text(content, metadata=base_meta)

        db_chunks: list[DocumentChunk] = []
        texts_to_embed: list[str] = []
        metas_to_embed: list[dict[str, Any]] = []
        ids_to_embed: list[str] = []

        for ch in chunks:
            chunk_meta = dict(ch.metadata)
            chunk_meta["chunk_index"] = ch.chunk_index
            chunk_meta["word_count"] = ch.word_count
            chunk_record = chunk_repo.create(
                document_id=doc.id,
                chunk_index=ch.chunk_index,
                content=ch.text,
                metadata=chunk_meta,
                word_count=ch.word_count,
            )
            db_chunks.append(chunk_record)

            texts_to_embed.append(ch.text)
            metas_to_embed.append(chunk_meta)
            ids_to_embed.append(chunk_record.chunk_id)

        # Index in vector store
        if texts_to_embed:
            self._vector_store.add_texts(
                texts=texts_to_embed,
                metadatas=metas_to_embed,
                ids=ids_to_embed,
            )

        self.db.commit()
        return doc, db_chunks

    def ingest_file(
        self,
        file_path: str | Path,
        name: Optional[str] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[Document, list[DocumentChunk]]:
        """Ingest a text or markdown file from the local file system."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        content = path.read_text(encoding="utf-8")
        doc_name = name or path.name
        file_meta = dict(metadata or {})
        file_meta["file_path"] = str(path.resolve())

        return self.ingest_text(
            name=doc_name,
            content=content,
            source_url=str(path),
            metadata=file_meta,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def get_document(self, document_id: str) -> Optional[Document]:
        return DocumentRepository(self.db).get_by_id(document_id)

    def get_document_by_name(self, name: str) -> Optional[Document]:
        return DocumentRepository(self.db).get_by_name(name)

    def list_documents(self, limit: int = 100, offset: int = 0) -> list[Document]:
        return DocumentRepository(self.db).get_all(limit=limit, offset=offset)

    def get_document_chunks(self, document_id: str) -> list[DocumentChunk]:
        return DocumentChunkRepository(self.db).get_by_document_id(document_id)

    def delete_document(self, document_id: str) -> bool:
        """Delete document, its chunks from DB, and remove its vectors from the vector store."""
        doc_repo = DocumentRepository(self.db)
        chunk_repo = DocumentChunkRepository(self.db)

        doc = doc_repo.get_by_id(document_id)
        if not doc:
            return False

        chunk_repo.delete_by_document_id(document_id)
        self._vector_store.delete_by_document_id(document_id)
        deleted = doc_repo.delete(document_id)
        self.db.commit()
        return deleted

    def search(
        self,
        query: str,
        top_k: int = 5,
        use_hybrid: bool = True,
    ) -> list[dict[str, Any]]:
        """Search documents using Hybrid retrieval (BM25 + vector search with RRF)."""
        if not query or not query.strip():
            return []

        # Collect corpus from DB chunks for BM25
        chunk_repo = DocumentChunkRepository(self.db)
        all_chunks = chunk_repo.get_all()

        if not all_chunks:
            # Fallback to vector store search directly
            return self._vector_store.similarity_search(query, k=top_k)

        bm25_corpus = [c.content or "" for c in all_chunks]

        retriever = HybridRetriever(
            vectorstore=self._vector_store,
            bm25_corpus=bm25_corpus,
            top_k=top_k,
        )
        return retriever.search(query)
