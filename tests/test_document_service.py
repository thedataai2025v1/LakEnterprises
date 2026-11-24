"""Integration tests for DocumentService (P4-1, P4-2, P4-3)."""

from pathlib import Path

import pytest

from lakenterprises.db import get_db_session, reset_db
from lakenterprises.document.vector_store import (DeterministicFakeEmbeddings,
                                                  InMemoryVectorStore)
from lakenterprises.services.document import DocumentService


@pytest.fixture(autouse=True)
def fresh_db() -> None:
    reset_db()
    yield


@pytest.fixture
def service() -> DocumentService:
    session = get_db_session()
    store = InMemoryVectorStore(DeterministicFakeEmbeddings(size=64))
    return DocumentService(db_session=session, vector_store=store)


class TestDocumentServiceIngestion:
    def test_ingest_text_creates_document_and_chunks(
        self, service: DocumentService
    ) -> None:
        content = (
            "Enterprise Policy 101.\n\n"
            "All employees must complete annual security awareness training. "
            "Access to customer data requires multi-factor authentication.\n\n"
            "Violations may result in disciplinary action up to termination."
        )
        doc, chunks = service.ingest_text(
            name="security_policy.md",
            content=content,
            source_url="internal://policies/security",
            metadata={"department": "Compliance"},
            chunk_size=120,
            chunk_overlap=20,
        )

        assert doc.id is not None
        assert doc.name == "security_policy.md"
        assert len(chunks) >= 2

        # Verify chunks persisted in database
        saved_chunks = service.get_document_chunks(doc.id)
        assert len(saved_chunks) == len(chunks)
        assert saved_chunks[0].document_id == doc.id
        assert saved_chunks[0].chunk_index == 0
        assert saved_chunks[0].word_count > 0

        # Verify indexed in vector store
        assert service._vector_store.count() == len(chunks)

    def test_ingest_file(self, service: DocumentService, tmp_path: Path) -> None:
        test_file = tmp_path / "system_architecture.txt"
        test_file.write_text(
            "System Architecture Overview:\n\n"
            "The platform leverages microservices communicating via gRPC and REST. "
            "Data persistence is managed via PostgreSQL and Redis.",
            encoding="utf-8",
        )

        doc, chunks = service.ingest_file(
            file_path=test_file,
            name="ArchOverview",
            chunk_size=100,
            chunk_overlap=15,
        )

        assert doc.name == "ArchOverview"
        assert len(chunks) >= 1
        assert service.get_document(doc.id) is not None

    def test_reingest_updates_existing_document(self, service: DocumentService) -> None:
        name = "handbook.md"
        service.ingest_text(name=name, content="Version 1 of the employee handbook.")
        assert service._vector_store.count() == 1

        # Re-ingest under the same name with new content
        doc_v2, chunks_v2 = service.ingest_text(
            name=name,
            content="Version 2 of the handbook.\n\nAdditional benefits added.",
            chunk_size=50,
            chunk_overlap=10,
        )

        assert doc_v2.name == name
        assert len(chunks_v2) >= 2
        # Vector store replaced previous chunks
        assert service._vector_store.count() == len(chunks_v2)


class TestDocumentServiceManagementAndSearch:
    def test_list_and_get_document(self, service: DocumentService) -> None:
        service.ingest_text(name="doc1", content="Content one")
        service.ingest_text(name="doc2", content="Content two")

        docs = service.list_documents()
        assert len(docs) == 2
        names = {d.name for d in docs}
        assert names == {"doc1", "doc2"}

    def test_delete_document_cleans_db_and_vector_store(
        self, service: DocumentService
    ) -> None:
        doc, chunks = service.ingest_text(
            name="to_delete.md",
            content="This document will be deleted.",
        )
        assert service.get_document(doc.id) is not None
        assert service._vector_store.count() >= 1

        deleted = service.delete_document(doc.id)
        assert deleted is True
        assert service.get_document(doc.id) is None
        assert service.get_document_chunks(doc.id) == []
        assert service._vector_store.count() == 0

    def test_search_retrieves_relevant_chunk(self, service: DocumentService) -> None:
        service.ingest_text(
            name="kubernetes_guide.md",
            content="Kubernetes cluster auto-scaling deploys additional worker nodes under high CPU load.",
        )
        service.ingest_text(
            name="gardening_tips.md",
            content="Tomatoes require full sunlight and daily watering during hot summer months.",
        )

        results = service.search(query="cluster worker nodes auto-scaling", top_k=2)
        assert len(results) >= 1
        top_text = results[0]["text"]
        assert "Kubernetes" in top_text or "cluster" in top_text
