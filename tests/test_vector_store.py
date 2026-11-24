"""Unit tests for P4-2: Vector store and deterministic embeddings."""

import math

import pytest

from lakenterprises.document.vector_store import (DeterministicFakeEmbeddings,
                                                  InMemoryVectorStore)


class TestDeterministicFakeEmbeddings:
    def test_embedding_dimension(self) -> None:
        emb = DeterministicFakeEmbeddings(size=64)
        vec = emb.embed_query("Hello world")
        assert len(vec) == 64

    def test_embedding_is_normalized(self) -> None:
        emb = DeterministicFakeEmbeddings(size=128)
        vec = emb.embed_query("Enterprise search query")
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-4

    def test_deterministic_reproducibility(self) -> None:
        emb = DeterministicFakeEmbeddings(size=128)
        v1 = emb.embed_query("Identical string")
        v2 = emb.embed_query("Identical string")
        assert v1 == v2

    def test_embed_documents_matches_individual(self) -> None:
        emb = DeterministicFakeEmbeddings(size=64)
        texts = ["Text one", "Text two"]
        batch = emb.embed_documents(texts)
        assert len(batch) == 2
        assert batch[0] == emb.embed_query("Text one")
        assert batch[1] == emb.embed_query("Text two")

    def test_semantic_overlap_similarity(self) -> None:
        emb = DeterministicFakeEmbeddings(size=128)
        q = emb.embed_query("PostgreSQL database connection pool")
        match_doc = emb.embed_query("database connection pool settings for PostgreSQL")
        unrelated_doc = emb.embed_query("astronomy telescope solar flare astrophysics")

        sim_match = sum(a * b for a, b in zip(q, match_doc))
        sim_unrelated = sum(a * b for a, b in zip(q, unrelated_doc))
        assert sim_match > sim_unrelated


class TestInMemoryVectorStore:
    @pytest.fixture
    def store(self) -> InMemoryVectorStore:
        return InMemoryVectorStore(DeterministicFakeEmbeddings(size=64))

    def test_empty_store_search(self, store: InMemoryVectorStore) -> None:
        results = store.similarity_search("anything")
        assert results == []

    def test_add_texts_and_count(self, store: InMemoryVectorStore) -> None:
        texts = ["Document A text", "Document B text", "Document C text"]
        ids = store.add_texts(
            texts, metadatas=[{"doc": "A"}, {"doc": "B"}, {"doc": "C"}]
        )
        assert len(ids) == 3
        assert store.count() == 3

    def test_similarity_search_returns_best_match(
        self, store: InMemoryVectorStore
    ) -> None:
        store.add_texts(
            [
                "FastAPI asynchronous routing and dependency injection",
                "Machine learning transformer neural network architectures",
                "Cooking organic pasta with tomato garlic basil sauce",
            ],
            ids=["tech-1", "tech-2", "food-1"],
            metadatas=[
                {"category": "backend"},
                {"category": "ai"},
                {"category": "cooking"},
            ],
        )

        results = store.similarity_search("FastAPI routing injection", k=1)
        assert len(results) == 1
        assert results[0]["id"] == "tech-1"

    def test_similarity_search_with_metadata_filter(
        self, store: InMemoryVectorStore
    ) -> None:
        store.add_texts(
            ["Security audit log report 2026", "Security firewall network update 2026"],
            ids=["s1", "s2"],
            metadatas=[{"dept": "finance"}, {"dept": "it"}],
        )

        results = store.similarity_search("Security", k=5, filter_dict={"dept": "it"})
        assert len(results) == 1
        assert results[0]["id"] == "s2"

    def test_delete_by_document_id(self, store: InMemoryVectorStore) -> None:
        store.add_texts(
            ["Chunk 1", "Chunk 2", "Chunk 3"],
            ids=["c1", "c2", "c3"],
            metadatas=[
                {"document_id": "doc-A"},
                {"document_id": "doc-A"},
                {"document_id": "doc-B"},
            ],
        )
        assert store.count() == 3

        deleted_count = store.delete_by_document_id("doc-A")
        assert deleted_count == 2
        assert store.count() == 1
        remaining = store.similarity_search("Chunk", k=5)
        assert remaining[0]["id"] == "c3"

    def test_clear(self, store: InMemoryVectorStore) -> None:
        store.add_texts(["A", "B"])
        assert store.count() == 2
        store.clear()
        assert store.count() == 0
