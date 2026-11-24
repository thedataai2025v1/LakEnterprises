"""Integration tests for Document API routes (P4-4)."""

import pytest
from fastapi.testclient import TestClient

from lakenterprises.app import create_app
from lakenterprises.db import reset_db
from lakenterprises.seed import seed_all


@pytest.fixture(autouse=True)
def setup_db() -> None:
    reset_db()
    seed_all()
    yield


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _get_token(client: TestClient, role: str) -> str:
    res = client.post(f"/api/v1/auth/demo/{role}")
    assert res.status_code == 200, f"Demo login failed for {role}: {res.text}"
    return res.json()["access_token"]


class TestDocumentRoutesRBAC:
    def test_unauthenticated_request_rejected(self, client: TestClient) -> None:
        res = client.get("/api/v1/documents")
        assert res.status_code == 401

    def test_viewer_cannot_ingest_document(self, client: TestClient) -> None:
        viewer_token = _get_token(client, "viewer")
        res = client.post(
            "/api/v1/documents/ingest",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"name": "test_doc", "content": "Sample content"},
        )
        assert res.status_code == 403

    def test_analyst_can_ingest_document(self, client: TestClient) -> None:
        analyst_token = _get_token(client, "analyst")
        res = client.post(
            "/api/v1/documents/ingest",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={
                "name": "ai_research.md",
                "content": "Graph RAG combines vector retrieval with Neo4j entity relationships.",
                "source_url": "https://lakenterprises.ai/docs",
                "chunk_size": 100,
                "chunk_overlap": 20,
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "ai_research.md"
        assert data["chunk_count"] >= 1
        assert "id" in data

    def test_viewer_can_list_and_get_document(self, client: TestClient) -> None:
        analyst_token = _get_token(client, "analyst")
        ingest_res = client.post(
            "/api/v1/documents/ingest",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={"name": "public_report.md", "content": "Q4 Earnings Summary."},
        )
        doc_id = ingest_res.json()["id"]

        viewer_token = _get_token(client, "viewer")
        list_res = client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert list_res.status_code == 200
        docs = list_res.json()
        assert any(d["id"] == doc_id for d in docs)

        get_res = client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "public_report.md"

    def test_analyst_cannot_delete_document(self, client: TestClient) -> None:
        analyst_token = _get_token(client, "analyst")
        ingest_res = client.post(
            "/api/v1/documents/ingest",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={"name": "to_protect.md", "content": "Sensitive document"},
        )
        doc_id = ingest_res.json()["id"]

        delete_res = client.delete(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        # Deletion is strictly reserved for admin
        assert delete_res.status_code == 403

    def test_admin_can_delete_document(self, client: TestClient) -> None:
        analyst_token = _get_token(client, "analyst")
        ingest_res = client.post(
            "/api/v1/documents/ingest",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={"name": "to_delete.md", "content": "Temporary content"},
        )
        doc_id = ingest_res.json()["id"]

        admin_token = _get_token(client, "admin")
        delete_res = client.delete(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert delete_res.status_code == 200
        assert "deleted successfully" in delete_res.json()["message"]

        # Verify not found now
        viewer_token = _get_token(client, "viewer")
        get_res = client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert get_res.status_code == 404

    def test_search_documents_endpoint(self, client: TestClient) -> None:
        analyst_token = _get_token(client, "analyst")
        client.post(
            "/api/v1/documents/ingest",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={
                "name": "microservices.md",
                "content": "Docker and Kubernetes provide container isolation and horizontal pod auto-scaling.",
            },
        )

        viewer_token = _get_token(client, "viewer")
        search_res = client.post(
            "/api/v1/documents/search",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"query": "Kubernetes container auto-scaling", "top_k": 3},
        )
        assert search_res.status_code == 200
        data = search_res.json()
        assert data["total_results"] >= 1
        assert "Kubernetes" in data["results"][0]["text"]
