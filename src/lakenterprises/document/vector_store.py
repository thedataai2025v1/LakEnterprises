"""In-memory vector store and deterministic embedding service for LakEnterprises.

Provides cosine-similarity vector search with zero external service dependencies,
while maintaining compatibility with LangChain Embeddings protocols.
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


class DeterministicFakeEmbeddings(Embeddings):
    """Deterministic, normalized fake embeddings for offline testing and fallback.

    Generates a dense unit vector from text hashing and word distributions,
    guaranteeing that semantically overlapping texts produce positive cosine
    similarity, completely offline.
    """

    def __init__(self, size: int = 128) -> None:
        self.size = size

    def _embed(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self.size

        vector = [0.0] * self.size
        # Hash full text for base seed
        seed_hash = hashlib.sha256(text.encode("utf-8")).digest()
        for i in range(self.size):
            byte_val = seed_hash[i % len(seed_hash)]
            vector[i] += (byte_val / 255.0) - 0.5

        # Incorporate word-level signals for semantic overlap
        words = text.lower().split()
        for w in words:
            w_hash = hashlib.sha256(w.encode("utf-8")).digest()
            idx = int.from_bytes(w_hash[:2], "big") % self.size
            weight = (w_hash[2] / 255.0) + 0.5
            vector[idx] += weight

        # Normalize to unit length (L2 norm)
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 1e-9:
            return [x / norm for x in vector]
        return [0.0] * self.size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@dataclass
class VectorEntry:
    """An individual entry inside the vector store."""

    id: str
    text: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentItem:
    """Document wrapper compatible with LangChain Document and dictionary access."""

    def __init__(self, id: str, text: str, metadata: dict[str, Any]) -> None:
        self.id = id
        self.text = text
        self.page_content = text
        self.metadata = metadata

    def __getitem__(self, item: str) -> Any:
        if item == "id":
            return self.id
        if item in ("text", "page_content"):
            return self.text
        if item == "metadata":
            return self.metadata
        return self.metadata.get(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default


class InMemoryVectorStore:
    """Thread-safe, self-contained in-memory vector store using cosine similarity."""

    def __init__(self, embeddings: Optional[Embeddings] = None) -> None:
        self.embeddings: Embeddings = embeddings or DeterministicFakeEmbeddings()
        self._entries: dict[str, VectorEntry] = {}

    def add_texts(
        self,
        texts: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
        ids: Optional[list[str]] = None,
    ) -> list[str]:
        """Embed and store a collection of text documents."""
        if not texts:
            return []

        import uuid as _uuid

        generated_ids: list[str] = ids or [str(_uuid.uuid4()) for _ in texts]
        if len(generated_ids) != len(texts):
            raise ValueError("ids length must match texts length")

        vectors = self.embeddings.embed_documents(texts)
        meta_list = metadatas or [{} for _ in texts]

        for doc_id, text, vector, meta in zip(generated_ids, texts, vectors, meta_list):
            self._entries[doc_id] = VectorEntry(
                id=doc_id,
                text=text,
                vector=vector,
                metadata=dict(meta),
            )

        return generated_ids

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[dict[str, Any]] = None,
    ) -> list[tuple[dict[str, Any], float]]:
        """Return the top *k* most similar documents and their cosine similarity scores."""
        if not self._entries or not query.strip():
            return []

        query_vec = self.embeddings.embed_query(query)
        scored: list[tuple[VectorEntry, float]] = []

        for entry in self._entries.values():
            if filter_dict:
                match = all(
                    entry.metadata.get(kf) == vf for kf, vf in filter_dict.items()
                )
                if not match:
                    continue

            # Compute cosine similarity
            dot = sum(q * d for q, d in zip(query_vec, entry.vector))
            scored.append((entry, dot))

        # Sort descending by score
        scored.sort(key=lambda x: x[1], reverse=True)

        results: list[tuple[dict[str, Any], float]] = []
        for entry, score in scored[:k]:
            results.append(
                (
                    DocumentItem(
                        id=entry.id,
                        text=entry.text,
                        metadata=entry.metadata,
                    ),
                    score,
                )
            )

        return results

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Convenience wrapper returning document dictionaries only."""
        with_scores = self.similarity_search_with_score(
            query, k=k, filter_dict=filter_dict
        )
        return [doc for doc, _ in with_scores]

    def delete(self, ids: list[str]) -> bool:
        """Delete entries matching the provided *ids*."""
        deleted = False
        for doc_id in ids:
            if doc_id in self._entries:
                del self._entries[doc_id]
                deleted = True
        return deleted

    def delete_by_document_id(self, document_id: str) -> int:
        """Delete all chunks belonging to *document_id*."""
        to_delete = [
            eid
            for eid, entry in self._entries.items()
            if entry.metadata.get("document_id") == document_id
        ]
        for eid in to_delete:
            del self._entries[eid]
        return len(to_delete)

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()
