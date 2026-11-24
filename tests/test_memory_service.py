"""Unit tests for MemoryService: recall, write-back, and PII scrubbing integration."""
# flake8: noqa: E402

import os
import tempfile

import pytest

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp()}"
from lakenterprises.db import get_db_session, init_db, reset_db  # noqa: E402
from lakenterprises.guardrails.pii_scrubber import PIIScrubber  # noqa: E402
from lakenterprises.memory.long_term_store import (
    LongTermProcessMemoryStore,
)  # noqa: E402
from lakenterprises.memory.models import (
    ChatMessage,  # noqa: E402
    LongTermMemoryItem,
    MemoryType,
    MessageRole,
    RecallRequest,
    WriteBackRequest,
)
from lakenterprises.memory.service import MemoryService  # noqa: E402
from lakenterprises.memory.session_store import ShortTermSessionStore  # noqa: E402

init_db()


@pytest.fixture(autouse=True)
def db():
    reset_db()
    session = get_db_session()
    yield session
    session.close()


def test_memory_service_recall_synthesis(db):
    session_store = ShortTermSessionStore(redis_client=None)
    long_term_store = LongTermProcessMemoryStore(session_factory=lambda: db)
    service = MemoryService(
        session_store=session_store,
        long_term_store=long_term_store,
    )

    session_id = "sess-recall-01"
    session_store.append_message(
        session_id,
        ChatMessage(role=MessageRole.USER, content="What are Acme's payment terms?"),
    )
    session_store.append_message(
        session_id,
        ChatMessage(role=MessageRole.ASSISTANT, content="Let me verify our records."),
    )

    long_term_store.store(
        LongTermMemoryItem(
            entity_type="customer",
            entity_id="CUST-ACME",
            key="payment_terms",
            content="Net-45 payment terms approved by CFO.",
            memory_type=MemoryType.PREFERENCE,
            importance=2.0,
        ),
        session=db,
    )

    res = service.recall(
        RecallRequest(
            session_id=session_id,
            entity_type="customer",
            entity_id="CUST-ACME",
        )
    )

    assert len(res.recent_messages) == 2
    assert len(res.long_term_memories) == 1
    assert "<enterprise_memory>" in res.synthesized_context
    assert "<session_history>" in res.synthesized_context
    assert "[user]: What are Acme's payment terms?" in res.synthesized_context
    assert "<durable_facts>" in res.synthesized_context
    assert "Net-45 payment terms approved by CFO." in res.synthesized_context


def test_memory_service_write_back_with_pii_scrubbing(db):
    session_store = ShortTermSessionStore(redis_client=None)
    long_term_store = LongTermProcessMemoryStore(session_factory=lambda: db)
    scrubber = PIIScrubber()
    service = MemoryService(
        session_store=session_store,
        long_term_store=long_term_store,
        scrubber=scrubber,
    )

    session_id = "sess-writeback-secure"
    # Turn containing AWS access key and card number
    msg = ChatMessage(
        role=MessageRole.USER,
        content="Here is my AWS key AKIA1111222233334444 and test card 5425233430109903 to file.",
        metadata={"user_phone": "415-555-2671"},
    )
    fact = LongTermMemoryItem(
        entity_type="customer",
        entity_id="CUST-999",
        key="secret_note",
        content="Backup API token is sk-abc123456789012345678901234567890.",
    )

    wb_res = service.write_back(
        WriteBackRequest(
            session_id=session_id,
            messages_to_append=[msg],
            long_term_items_to_store=[fact],
            session_variables={"api_key": "sk-abc123456789012345678901234567890"},
            scrub_secrets=True,
        )
    )

    assert wb_res.success is True
    assert wb_res.scrubbed is True
    assert wb_res.redacted_items_count >= 2

    # Verify session store does not contain plaintext secret
    saved_history = session_store.get_history(session_id)
    assert len(saved_history) == 1
    assert "AKIA1111222233334444" not in saved_history[0].content
    assert "[REDACTED_AWS_KEY]" in saved_history[0].content
    assert "5425233430109903" not in saved_history[0].content
    assert "[REDACTED_CREDIT_CARD]" in saved_history[0].content
    assert saved_history[0].metadata["user_phone"] == "[REDACTED_PHONE]"

    # Verify long-term store does not contain plaintext OpenAI key
    saved_facts = long_term_store.query(
        entity_type="customer", entity_id="CUST-999", session=db
    )
    assert len(saved_facts) == 1
    assert "sk-abc123456789012345678901234567890" not in saved_facts[0].content
    assert (
        "[REDACTED_API_KEY]" in saved_facts[0].content
        or "[REDACTED_OPENAI_KEY]" in saved_facts[0].content
    )
