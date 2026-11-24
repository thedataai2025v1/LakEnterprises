"""Unit tests for LongTermProcessMemoryStore and ProcessMemoryRepository."""
# flake8: noqa: E402

import os
import tempfile

import pytest

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp()}"
from lakenterprises.db import get_db_session, init_db, reset_db  # noqa: E402
from lakenterprises.memory.long_term_store import (
    LongTermProcessMemoryStore,
)  # noqa: E402
from lakenterprises.memory.models import LongTermMemoryItem  # noqa: E402
from lakenterprises.memory.models import MemoryType
from lakenterprises.repositories import ProcessMemoryRepository  # noqa: E402

init_db()


@pytest.fixture(autouse=True)
def db():
    reset_db()
    session = get_db_session()
    yield session
    session.close()


def test_process_memory_repo_crud(db):
    repo = ProcessMemoryRepository(db)

    item = repo.create(
        entity_type="customer",
        entity_id="CUST-1001",
        key="payment_terms",
        content="Customer requires Net-30 payment terms.",
        memory_type="preference",
        importance=2.0,
        metadata={"source": "sales_call"},
    )
    assert item.id is not None
    assert item.key == "payment_terms"
    assert item.importance == 2.0

    found = repo.get_by_id(item.id)
    assert found is not None
    assert found.content == "Customer requires Net-30 payment terms."

    found_key = repo.get_by_key("customer", "CUST-1001", "payment_terms")
    assert found_key is not None
    assert found_key.id == item.id


def test_process_memory_upsert(db):
    repo = ProcessMemoryRepository(db)

    i1 = repo.upsert(
        entity_type="vendor",
        entity_id="VEND-202",
        key="discount_rate",
        content="Initial rate 5%",
        importance=1.0,
    )
    assert i1.content == "Initial rate 5%"

    # Update via upsert
    i2 = repo.upsert(
        entity_type="vendor",
        entity_id="VEND-202",
        key="discount_rate",
        content="Negotiated rate 12%",
        importance=2.5,
    )
    assert i2.id == i1.id
    assert i2.content == "Negotiated rate 12%"
    assert i2.importance == 2.5


def test_long_term_store_query_and_search(db):
    store = LongTermProcessMemoryStore(session_factory=lambda: db)

    items = [
        LongTermMemoryItem(
            entity_type="process",
            entity_id="PROC-900",
            key="server_spec",
            content="Standard web server requires 32GB RAM and 8 vCPUs.",
            memory_type=MemoryType.FACT,
            importance=1.0,
        ),
        LongTermMemoryItem(
            entity_type="process",
            entity_id="PROC-900",
            key="incident_learning",
            content="Database pool exhaustion mitigated by connection limits.",
            memory_type=MemoryType.LEARNING,
            importance=3.0,
        ),
        LongTermMemoryItem(
            entity_type="customer",
            entity_id="CUST-888",
            key="sla_tier",
            content="Platinum SLA tier with 1 hour response time.",
            memory_type=MemoryType.PREFERENCE,
            importance=4.0,
        ),
    ]

    stored = store.store_batch(items, session=db)
    assert len(stored) == 3

    # Query by entity
    proc_memories = store.query(entity_type="process", entity_id="PROC-900", session=db)
    assert len(proc_memories) == 2
    # Order by importance descending
    assert proc_memories[0].importance == 3.0
    assert proc_memories[1].importance == 1.0

    # Search by keyword
    search_results = store.search("exhaustion", session=db)
    assert len(search_results) == 1
    assert search_results[0].key == "incident_learning"


def test_long_term_store_deletion(db):
    store = LongTermProcessMemoryStore(session_factory=lambda: db)

    item = store.store(
        LongTermMemoryItem(
            entity_type="incident",
            entity_id="INC-505",
            key="root_cause",
            content="Memory leak in worker pool",
        ),
        session=db,
    )

    deleted = store.delete(item.id, session=db)
    assert deleted is True

    not_found = store.get_by_id(item.id, session=db)
    assert not_found is None
