"""Integration tests for FastAPI Memory router endpoints."""

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp()}"
from lakenterprises.db import init_db, reset_db  # noqa: E402
from lakenterprises.memory.routes import router as memory_router  # noqa: E402

init_db()


@pytest.fixture(scope="module")
def client():
    reset_db()
    app = FastAPI()
    app.include_router(memory_router)
    return TestClient(app)


def test_api_session_lifecycle(client):
    session_id = "api-session-123"

    # Append message
    res = client.post(
        f"/api/v1/memory/sessions/{session_id}/messages",
        json={"role": "user", "content": "How do I trigger an approval?"},
    )
    assert res.status_code == 201
    assert res.json()["status"] == "ok"

    # Set variables
    res_var = client.post(
        f"/api/v1/memory/sessions/{session_id}/variables",
        json={"active_role": "analyst", "process_id": "PROC-10"},
    )
    assert res_var.status_code == 200
    assert "active_role" in res_var.json()["keys"]

    # Get session
    res_get = client.get(f"/api/v1/memory/sessions/{session_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert len(data["messages"]) == 1
    assert data["variables"]["active_role"] == "analyst"

    # Clear session
    res_del = client.delete(f"/api/v1/memory/sessions/{session_id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "cleared"


def test_api_long_term_memory(client):
    item_payload = {
        "entity_type": "customer",
        "entity_id": "CUST-API",
        "key": "discount_rate",
        "content": "Eligible for 15% tier 1 volume discount",
        "importance": 2.0,
    }

    res_post = client.post("/api/v1/memory/long-term", json=item_payload)
    assert res_post.status_code == 201
    mem_id = res_post.json()["id"]
    assert mem_id is not None

    # Query
    res_query = client.get(
        "/api/v1/memory/long-term?entity_type=customer&entity_id=CUST-API"
    )
    assert res_query.status_code == 200
    items = res_query.json()
    assert len(items) == 1
    assert items[0]["key"] == "discount_rate"

    # Delete
    res_del = client.delete(f"/api/v1/memory/long-term/{mem_id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "deleted"


def test_api_recall_and_write_back(client):
    session_id = "api-session-recall"

    # Write-back
    wb_payload = {
        "session_id": session_id,
        "messages_to_append": [
            {"role": "user", "content": "My email is test@company.com with pass123"}
        ],
        "long_term_items_to_store": [
            {
                "entity_type": "customer",
                "entity_id": "CUST-WB",
                "key": "region",
                "content": "Customer based in EMEA region",
            }
        ],
        "scrub_secrets": True,
    }
    res_wb = client.post("/api/v1/memory/write-back", json=wb_payload)
    assert res_wb.status_code == 200
    assert res_wb.json()["success"] is True

    # Recall
    res_rec = client.post(
        "/api/v1/memory/recall",
        json={
            "session_id": session_id,
            "entity_type": "customer",
            "entity_id": "CUST-WB",
        },
    )
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert len(rec_data["recent_messages"]) == 1
    assert len(rec_data["long_term_memories"]) == 1
    assert "<enterprise_memory>" in rec_data["synthesized_context"]
    assert "EMEA region" in rec_data["synthesized_context"]
