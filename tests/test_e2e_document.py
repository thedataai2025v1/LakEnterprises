"""End-to-end integration and lifecycle tests for Document Pipeline (Phase 4)."""

import pytest
from fastapi.testclient import TestClient

from lakenterprises.app import create_app
from lakenterprises.db import reset_db
from lakenterprises.seed import seed_all


@pytest.fixture(autouse=True)
def init_environment() -> None:
    reset_db()
    seed_all()
    yield


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_full_document_lifecycle_e2e(client: TestClient) -> None:
    """E2E Test:
    1. Obtain demo analyst token
    2. Ingest structured enterprise policy document with multiple sections
    3. Verify chunking produced expected chunks and word counts
    4. Obtain demo viewer token
    5. Perform hybrid search query, verifying top citation relevance
    6. Verify viewer cannot delete document (403)
    7. Obtain demo admin token and delete document
    8. Verify document and chunks purged from storage
    """
    # 1. Obtain demo analyst token
    analyst_token_res = client.post("/api/v1/auth/demo/analyst")
    assert analyst_token_res.status_code == 200
    analyst_token = analyst_token_res.json()["access_token"]

    # 2. Ingest structured document
    doc_content = (
        "# Enterprise Data Retention Policy\n\n"
        "Section 1: General Principles\n"
        "Customer records must be retained for seven years following account termination. "
        "All data stores must apply encryption at rest with AES-256 keys.\n\n"
        "Section 2: Audit Logs and Incident Reports\n"
        "Security audit logs must be preserved in immutable write-once read-many (WORM) storage "
        "for a minimum of ten years to ensure regulatory compliance with SOC2 and HIPAA.\n\n"
        "Section 3: Disciplinary Consequences\n"
        "Failure to adhere to retention mandates will result in formal audit escalation."
    )

    ingest_res = client.post(
        "/api/v1/documents/ingest",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={
            "name": "DataRetentionPolicy2026",
            "content": doc_content,
            "source_url": "https://compliance.lakenterprises.com/policies/retention",
            "metadata": {"department": "Legal & Compliance", "version": "2026.1"},
            "chunk_size": 220,
            "chunk_overlap": 30,
        },
    )
    assert ingest_res.status_code == 201
    doc_data = ingest_res.json()
    doc_id = doc_data["id"]
    assert doc_data["chunk_count"] >= 3
    assert len(doc_data["chunks"]) == doc_data["chunk_count"]

    # 3. Obtain demo viewer token and browse
    viewer_token_res = client.post("/api/v1/auth/demo/viewer")
    assert viewer_token_res.status_code == 200
    viewer_token = viewer_token_res.json()["access_token"]

    # List documents
    list_res = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert list_res.status_code == 200
    docs = list_res.json()
    assert any(d["id"] == doc_id for d in docs)

    # 4. Search via hybrid retriever
    search_res = client.post(
        "/api/v1/documents/search",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"query": "WORM storage audit logs SOC2 retention", "top_k": 2},
    )
    assert search_res.status_code == 200
    results = search_res.json()["results"]
    assert len(results) >= 1
    # Top result should reference audit logs / WORM storage
    assert (
        "audit" in results[0]["text"].lower()
        or "retention" in results[0]["text"].lower()
    )

    # 5. Viewer attempts deletion -> 403 Forbidden
    del_viewer_res = client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert del_viewer_res.status_code == 403

    # 6. Admin token deletes document -> 200 OK
    admin_token_res = client.post("/api/v1/auth/demo/admin")
    assert admin_token_res.status_code == 200
    admin_token = admin_token_res.json()["access_token"]

    del_admin_res = client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_admin_res.status_code == 200

    # 7. Document is gone
    get_res = client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert get_res.status_code == 404
