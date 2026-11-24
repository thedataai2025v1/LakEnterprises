"""Unit tests for ShortTermSessionStore with in-memory and Redis mock."""

from lakenterprises.memory.models import ChatMessage, MessageRole
from lakenterprises.memory.session_store import ShortTermSessionStore


def test_session_store_append_and_get_history():
    store = ShortTermSessionStore(redis_client=None)
    session_id = "test-session-001"

    store.append_message(
        session_id,
        ChatMessage(role=MessageRole.USER, content="Hello, can you check order 9001?"),
    )
    store.append_message(
        session_id,
        ChatMessage(role=MessageRole.ASSISTANT, content="Looking up order 9001 now."),
    )

    history = store.get_history(session_id)
    assert len(history) == 2
    assert history[0].role == MessageRole.USER
    assert history[0].content == "Hello, can you check order 9001?"
    assert history[1].role == MessageRole.ASSISTANT
    assert history[1].content == "Looking up order 9001 now."


def test_session_store_sliding_window_pruning():
    store = ShortTermSessionStore(redis_client=None, max_history_window=3)
    session_id = "test-session-prune"

    for i in range(5):
        store.append_message(
            session_id,
            ChatMessage(role=MessageRole.USER, content=f"Message {i}"),
        )

    history = store.get_history(session_id)
    assert len(history) == 3
    assert history[0].content == "Message 2"
    assert history[1].content == "Message 3"
    assert history[2].content == "Message 4"


def test_session_store_variables():
    store = ShortTermSessionStore(redis_client=None)
    session_id = "test-session-vars"

    store.set_variable(session_id, "customer_id", "CUST-404")
    store.set_variable(session_id, "discount_tier", 0.15)
    store.set_variables(session_id, {"status": "in_progress", "retry_count": 2})

    assert store.get_variable(session_id, "customer_id") == "CUST-404"
    assert store.get_variable(session_id, "discount_tier") == 0.15
    assert store.get_variable(session_id, "status") == "in_progress"
    assert store.get_variable(session_id, "nonexistent", default="none") == "none"

    all_vars = store.get_all_variables(session_id)
    assert all_vars["customer_id"] == "CUST-404"
    assert all_vars["discount_tier"] == 0.15
    assert all_vars["retry_count"] == 2


def test_session_store_get_session_and_clear():
    store = ShortTermSessionStore(redis_client=None)
    session_id = "test-session-full"

    store.append_message(
        session_id,
        ChatMessage(role=MessageRole.USER, content="Querying inventory."),
    )
    store.set_variable(session_id, "item_sku", "SKU-999")

    context = store.get_session(session_id)
    assert context.session_id == session_id
    assert len(context.messages) == 1
    assert context.variables["item_sku"] == "SKU-999"

    cleared = store.clear_session(session_id)
    assert cleared is True
    assert len(store.get_history(session_id)) == 0
    assert store.get_all_variables(session_id) == {}


def test_session_store_offset_and_limit():
    store = ShortTermSessionStore(redis_client=None)
    session_id = "test-session-paging"

    for i in range(10):
        store.append_message(
            session_id,
            ChatMessage(role=MessageRole.USER, content=f"Step {i}"),
        )

    recent_3 = store.get_history(session_id, limit=3)
    assert len(recent_3) == 3
    assert recent_3[0].content == "Step 7"
    assert recent_3[2].content == "Step 9"

    offset_history = store.get_history(session_id, offset=5)
    assert len(offset_history) == 5
    assert offset_history[0].content == "Step 5"
