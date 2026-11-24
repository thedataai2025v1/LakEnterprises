"""End-to-end multi-turn enterprise memory test."""

# flake8: noqa: E402

import os
import tempfile

import pytest

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp()}"
from lakenterprises.db import get_db_session, init_db, reset_db  # noqa: E402
from lakenterprises.memory import (
    ChatMessage,  # noqa: E402
    LongTermMemoryItem,
    MemoryService,
    MemoryType,
    MessageRole,
    RecallRequest,
    ShortTermSessionStore,
    WriteBackRequest,
)
from lakenterprises.memory.long_term_store import (
    LongTermProcessMemoryStore,
)  # noqa: E402

init_db()


@pytest.fixture(autouse=True)
def db():
    reset_db()
    session = get_db_session()
    yield session
    session.close()


def test_e2e_enterprise_memory_flow(db):
    """E2E Scenario: Multi-turn interaction, credential sanitization, long-term learning, and cross-session recall."""
    session_store = ShortTermSessionStore(redis_client=None)
    long_term_store = LongTermProcessMemoryStore(session_factory=lambda: db)
    service = MemoryService(
        session_store=session_store, long_term_store=long_term_store
    )

    session_1 = "cust-session-day1"
    customer_id = "CUST-GLOBAL-77"

    # Turn 1: Customer describes purchase intent and leaks a sensitive token
    user_msg_1 = ChatMessage(
        role=MessageRole.USER,
        content=(
            "Hi, we want to renew our enterprise cloud license for $45,000. "
            "Our billing contact is billing@global77.com. "
            "Please use our temp AWS key AKIA9999888877776666 for verification."
        ),
    )
    asst_msg_1 = ChatMessage(
        role=MessageRole.ASSISTANT,
        content="I have noted your enterprise renewal. Let me check your SLA tier.",
    )

    wb_1 = service.write_back(
        WriteBackRequest(
            session_id=session_1,
            messages_to_append=[user_msg_1, asst_msg_1],
            session_variables={"renewal_stage": "negotiation", "amount": 45000.0},
            scrub_secrets=True,
        )
    )
    assert wb_1.success is True
    assert wb_1.redacted_items_count >= 1

    # Turn 2: Customer specifies strict corporate policy (durable fact)
    learned_policy = LongTermMemoryItem(
        entity_type="customer",
        entity_id=customer_id,
        key="invoicing_protocol",
        content="Corporate compliance demands PO approval and dual sign-off before invoice dispatch.",
        memory_type=MemoryType.PREFERENCE,
        importance=3.0,
    )

    wb_2 = service.write_back(
        WriteBackRequest(
            session_id=session_1,
            long_term_items_to_store=[learned_policy],
            scrub_secrets=True,
        )
    )
    assert wb_2.long_term_items_saved == 1

    # Day 2: New session initialized by another agent/analyst
    session_2 = "cust-session-day2"

    recall_res = service.recall(
        RecallRequest(
            session_id=session_2,  # New session has no messages yet
            query="renewal",
            entity_type="customer",
            entity_id=customer_id,
        )
    )

    # Context contains durable knowledge learned on Day 1
    assert len(recall_res.recent_messages) == 0
    assert len(recall_res.long_term_memories) == 1
    assert "invoicing_protocol" in recall_res.synthesized_context
    assert "dual sign-off" in recall_res.synthesized_context

    # Verify session 1 messages were scrubbed permanently
    s1_history = session_store.get_history(session_1)
    assert "AKIA9999888877776666" not in s1_history[0].content
    assert "[REDACTED_AWS_KEY]" in s1_history[0].content
