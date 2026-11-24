"""Short-term session memory store backed by Redis with in-memory fallback."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from lakenterprises.config import settings
from lakenterprises.memory.models import ChatMessage, SessionContext

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ShortTermSessionStore:
    """Manages ephemeral conversation turns and session variables in Redis or in-memory."""

    def __init__(
        self,
        redis_client: Optional[object] = None,
        default_ttl: int = 86400,
        max_history_window: int = 50,
    ) -> None:
        self.default_ttl = default_ttl
        self.max_history_window = max_history_window
        self._redis = redis_client
        self._memory_sessions: Dict[str, Dict[str, Any]] = {}

        if self._redis is None:
            self._init_redis_client()

    def _init_redis_client(self) -> None:
        if settings.cache_store == "redis" and settings.redis_url:
            try:
                import redis

                client = redis.from_url(settings.redis_url, decode_responses=True)
                client.ping()
                self._redis = client
                logger.info(
                    "Connected to Redis for session memory at %s", settings.redis_url
                )
            except Exception as e:
                logger.info(
                    "Redis not available for session memory (%s), using in-memory store",
                    e,
                )
                self._redis = None

    def _key_messages(self, session_id: str) -> str:
        return f"session:{session_id}:messages"

    def _key_vars(self, session_id: str) -> str:
        return f"session:{session_id}:vars"

    def _key_meta(self, session_id: str) -> str:
        return f"session:{session_id}:meta"

    def append_message(
        self,
        session_id: str,
        message: ChatMessage,
        ttl: Optional[int] = None,
    ) -> None:
        """Append a message turn to the short-term session store."""
        expiry = ttl or self.default_ttl
        msg_payload = message.model_dump_json()

        if self._redis is not None:
            try:
                k_msg = self._key_messages(session_id)
                k_meta = self._key_meta(session_id)
                pipe = self._redis.pipeline()
                pipe.rpush(k_msg, msg_payload)
                pipe.expire(k_msg, expiry)
                pipe.hset(k_meta, mapping={"updated_at": _now_utc().isoformat()})
                pipe.expire(k_meta, expiry)
                pipe.execute()
                self.prune_history(session_id, self.max_history_window)
                return
            except Exception as e:
                logger.warning(
                    "Redis append_message failed, using in-memory fallback: %s", e
                )

        # In-memory fallback
        if session_id not in self._memory_sessions:
            now = _now_utc()
            self._memory_sessions[session_id] = {
                "created_at": now,
                "updated_at": now,
                "messages": [],
                "variables": {},
                "ttl": expiry,
            }
        sess = self._memory_sessions[session_id]
        sess["messages"].append(message)
        sess["updated_at"] = _now_utc()
        if len(sess["messages"]) > self.max_history_window:
            sess["messages"] = sess["messages"][-self.max_history_window :]

    def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[ChatMessage]:
        """Retrieve recent message history for a session."""
        if self._redis is not None:
            try:
                k_msg = self._key_messages(session_id)
                raw_items = self._redis.lrange(k_msg, 0, -1)
                messages: List[ChatMessage] = []
                for item in raw_items:
                    data = json.loads(item)
                    messages.append(ChatMessage.model_validate(data))
                if offset:
                    messages = messages[offset:]
                if limit is not None:
                    messages = messages[-limit:]
                return messages
            except Exception as e:
                logger.warning(
                    "Redis get_history failed, using in-memory fallback: %s", e
                )

        # In-memory fallback
        sess = self._memory_sessions.get(session_id)
        if not sess:
            return []
        msgs = sess["messages"]
        if offset:
            msgs = msgs[offset:]
        if limit is not None:
            msgs = msgs[-limit:]
        return list(msgs)

    def set_variable(
        self,
        session_id: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Store a working memory variable in the session."""
        expiry = ttl or self.default_ttl
        val_str = json.dumps(value)

        if self._redis is not None:
            try:
                k_vars = self._key_vars(session_id)
                pipe = self._redis.pipeline()
                pipe.hset(k_vars, key, val_str)
                pipe.expire(k_vars, expiry)
                pipe.execute()
                return
            except Exception as e:
                logger.warning(
                    "Redis set_variable failed, using in-memory fallback: %s", e
                )

        # In-memory fallback
        if session_id not in self._memory_sessions:
            now = _now_utc()
            self._memory_sessions[session_id] = {
                "created_at": now,
                "updated_at": now,
                "messages": [],
                "variables": {},
                "ttl": expiry,
            }
        self._memory_sessions[session_id]["variables"][key] = value

    def set_variables(
        self,
        session_id: str,
        variables: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """Store multiple working memory variables in the session."""
        for k, v in variables.items():
            self.set_variable(session_id, k, v, ttl=ttl)

    def get_variable(self, session_id: str, key: str, default: Any = None) -> Any:
        """Retrieve a single session variable."""
        if self._redis is not None:
            try:
                k_vars = self._key_vars(session_id)
                val_str = self._redis.hget(k_vars, key)
                if val_str is not None:
                    return json.loads(val_str)
                return default
            except Exception as e:
                logger.warning(
                    "Redis get_variable failed, using in-memory fallback: %s", e
                )

        # In-memory fallback
        sess = self._memory_sessions.get(session_id)
        if not sess:
            return default
        return sess["variables"].get(key, default)

    def get_all_variables(self, session_id: str) -> Dict[str, Any]:
        """Retrieve all working memory variables for a session."""
        if self._redis is not None:
            try:
                k_vars = self._key_vars(session_id)
                raw_dict = self._redis.hgetall(k_vars)
                result = {}
                for k, v in raw_dict.items():
                    try:
                        result[k] = json.loads(v)
                    except Exception:
                        result[k] = v
                return result
            except Exception as e:
                logger.warning(
                    "Redis get_all_variables failed, using in-memory fallback: %s", e
                )

        # In-memory fallback
        sess = self._memory_sessions.get(session_id)
        if not sess:
            return {}
        return dict(sess["variables"])

    def get_session(self, session_id: str) -> SessionContext:
        """Retrieve full session context including messages and variables."""
        msgs = self.get_history(session_id)
        vars_dict = self.get_all_variables(session_id)

        now = _now_utc()
        created_at = now
        updated_at = now

        if self._redis is not None:
            try:
                k_meta = self._key_meta(session_id)
                meta = self._redis.hgetall(k_meta)
                if meta.get("created_at"):
                    created_at = datetime.fromisoformat(meta["created_at"])
                if meta.get("updated_at"):
                    updated_at = datetime.fromisoformat(meta["updated_at"])
            except Exception:
                pass
        else:
            sess = self._memory_sessions.get(session_id)
            if sess:
                created_at = sess.get("created_at", now)
                updated_at = sess.get("updated_at", now)

        return SessionContext(
            session_id=session_id,
            messages=msgs,
            variables=vars_dict,
            created_at=created_at,
            updated_at=updated_at,
            ttl_seconds=self.default_ttl,
        )

    def clear_session(self, session_id: str) -> bool:
        """Clear all messages, variables, and metadata for a session."""
        if self._redis is not None:
            try:
                keys = [
                    self._key_messages(session_id),
                    self._key_vars(session_id),
                    self._key_meta(session_id),
                ]
                self._redis.delete(*keys)
                return True
            except Exception as e:
                logger.warning("Redis clear_session failed: %s", e)

        # In-memory
        if session_id in self._memory_sessions:
            del self._memory_sessions[session_id]
            return True
        return False

    def prune_history(self, session_id: str, max_messages: int = 50) -> int:
        """Keep only the latest `max_messages` in session history."""
        if self._redis is not None:
            try:
                k_msg = self._key_messages(session_id)
                total = self._redis.llen(k_msg)
                if total > max_messages:
                    start_idx = total - max_messages
                    self._redis.ltrim(k_msg, start_idx, -1)
                    return total - max_messages
                return 0
            except Exception as e:
                logger.warning("Redis prune_history failed: %s", e)

        sess = self._memory_sessions.get(session_id)
        if sess and len(sess["messages"]) > max_messages:
            trimmed = len(sess["messages"]) - max_messages
            sess["messages"] = sess["messages"][-max_messages:]
            return trimmed
        return 0


# Default global instance
default_session_store = ShortTermSessionStore()
