"""In-memory mock adapter for transactional email and alerting dispatch."""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional


class MockEmailAdapter:
    """Mock transactional email service recording outbound emails in an in-memory queue."""

    def __init__(self, simulate_outage: bool = False) -> None:
        self.simulate_outage = simulate_outage
        self.outbox: List[Dict[str, Any]] = []

    def _check_outage(self) -> None:
        if self.simulate_outage:
            raise ConnectionError("Email Service unavailable (simulated outage).")

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        self._check_outage()
        msg_id = f"msg-{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        message: Dict[str, Any] = {
            "message_id": msg_id,
            "to": to,
            "subject": subject,
            "body": body,
            "cc": cc or [],
            "sent_at": now,
            "status": "delivered",
        }
        self.outbox.append(message)
        return message

    def get_sent_emails(
        self,
        recipient: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self._check_outage()
        if recipient:
            return [m for m in self.outbox if m.get("to") == recipient]
        return list(self.outbox)

    def clear_outbox(self) -> None:
        self.outbox.clear()
