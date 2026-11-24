"""Memory orchestration service combining short-term sessions and durable facts."""

from __future__ import annotations

import logging
from typing import List, Optional

from lakenterprises.guardrails.pii_scrubber import PIIScrubber, default_scrubber
from lakenterprises.memory.long_term_store import (
    LongTermProcessMemoryStore,
    default_long_term_store,
)
from lakenterprises.memory.models import (
    ChatMessage,
    LongTermMemoryItem,
    RecallRequest,
    RecallResponse,
    WriteBackRequest,
    WriteBackResponse,
)
from lakenterprises.memory.session_store import (
    ShortTermSessionStore,
    default_session_store,
)

logger = logging.getLogger(__name__)


class MemoryService:
    """Enterprise memory orchestration service with PII scrubbing and context recall."""

    def __init__(
        self,
        session_store: Optional[ShortTermSessionStore] = None,
        long_term_store: Optional[LongTermProcessMemoryStore] = None,
        scrubber: Optional[PIIScrubber] = None,
    ) -> None:
        self.session_store = session_store or default_session_store
        self.long_term_store = long_term_store or default_long_term_store
        self.scrubber = scrubber or default_scrubber

    def recall(self, request: RecallRequest) -> RecallResponse:
        """Recall relevant conversation history and enterprise facts for an agent."""
        recent_messages: List[ChatMessage] = []
        if request.session_id:
            recent_messages = self.session_store.get_history(
                session_id=request.session_id,
                limit=request.max_session_messages,
            )

        long_term_memories: List[LongTermMemoryItem] = []
        if request.entity_type and request.entity_id:
            long_term_memories = self.long_term_store.query(
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                min_importance=request.min_importance,
                limit=request.max_long_term_items,
            )
        elif request.query:
            long_term_memories = self.long_term_store.search(
                query_text=request.query,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                min_importance=request.min_importance,
                limit=request.max_long_term_items,
            )

        # Build synthesized context block for agent prompt injection
        context_parts: List[str] = ["<enterprise_memory>"]

        if recent_messages:
            context_parts.append("  <session_history>")
            for msg in recent_messages:
                role_val = (
                    msg.role.value if hasattr(msg.role, "value") else str(msg.role)
                )
                context_parts.append(f"    [{role_val}]: {msg.content}")
            context_parts.append("  </session_history>")

        if long_term_memories:
            context_parts.append("  <durable_facts>")
            for item in long_term_memories:
                m_type = (
                    item.memory_type.value
                    if hasattr(item.memory_type, "value")
                    else str(item.memory_type)
                )
                context_parts.append(
                    f"    - [{item.entity_type}:{item.entity_id} | {m_type}] "
                    f"({item.key}, imp={item.importance}): {item.content}"
                )
            context_parts.append("  </durable_facts>")

        context_parts.append("</enterprise_memory>")
        synthesized_context = "\n".join(context_parts)

        return RecallResponse(
            session_id=request.session_id,
            recent_messages=recent_messages,
            long_term_memories=long_term_memories,
            synthesized_context=synthesized_context,
        )

    def write_back(self, request: WriteBackRequest) -> WriteBackResponse:
        """Sanitize secrets and write conversation turns and facts into memory stores."""
        redacted_count = 0
        messages_to_save: List[ChatMessage] = []

        for msg in request.messages_to_append:
            content = msg.content
            if request.scrub_secrets:
                res = self.scrubber.scrub_text(content)
                content = res.scrubbed_text
                redacted_count += len(res.detections)

            metadata = msg.metadata
            if request.scrub_secrets and metadata:
                metadata = self.scrubber.scrub_dict(metadata)

            messages_to_save.append(
                ChatMessage(
                    role=msg.role,
                    content=content,
                    timestamp=msg.timestamp,
                    metadata=metadata,
                )
            )

        # Persist messages in session store
        messages_added = 0
        if request.session_id and messages_to_save:
            for m in messages_to_save:
                self.session_store.append_message(request.session_id, m)
                messages_added += 1

        # Store session variables
        if request.session_id and request.session_variables:
            vars_to_save = request.session_variables
            if request.scrub_secrets:
                vars_to_save = self.scrubber.scrub_dict(vars_to_save)
            self.session_store.set_variables(request.session_id, vars_to_save)

        # Sanitize and persist long-term memories
        items_to_save: List[LongTermMemoryItem] = []
        for item in request.long_term_items_to_store:
            content = item.content
            if request.scrub_secrets:
                res = self.scrubber.scrub_text(content)
                content = res.scrubbed_text
                redacted_count += len(res.detections)

            metadata = item.metadata
            if request.scrub_secrets and metadata:
                metadata = self.scrubber.scrub_dict(metadata)

            items_to_save.append(
                LongTermMemoryItem(
                    id=item.id,
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                    memory_type=item.memory_type,
                    key=item.key,
                    content=content,
                    importance=item.importance,
                    metadata=metadata,
                )
            )

        long_term_items_saved = 0
        if items_to_save:
            saved_items = self.long_term_store.store_batch(items_to_save)
            long_term_items_saved = len(saved_items)

        return WriteBackResponse(
            success=True,
            session_id=request.session_id,
            messages_added=messages_added,
            long_term_items_saved=long_term_items_saved,
            scrubbed=request.scrub_secrets,
            redacted_items_count=redacted_count,
        )


default_memory_service = MemoryService()
