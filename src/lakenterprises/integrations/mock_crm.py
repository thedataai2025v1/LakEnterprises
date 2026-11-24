"""In-memory mock adapter for CRM systems (Salesforce / HubSpot / Zendesk)."""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional


class MockCRMAdapter:
    """Mock CRM implementation providing customers, accounts, and support tickets."""

    def __init__(self, simulate_outage: bool = False) -> None:
        self.simulate_outage = simulate_outage
        self.customers: Dict[str, Dict[str, Any]] = {
            "CUST-101": {
                "customer_id": "CUST-101",
                "name": "Acme Global Industries",
                "domain": "acmeglobal.com",
                "email": "contact@acmeglobal.com",
                "tier": "enterprise",
                "arr_usd": 250000.0,
                "status": "active",
                "primary_contact": "Alice Henderson (VP IT)",
                "sla_tier": "gold",
            },
            "CUST-102": {
                "customer_id": "CUST-102",
                "name": "Wayne Enterprises",
                "domain": "waynecorp.com",
                "email": "procurement@waynecorp.com",
                "tier": "vip",
                "arr_usd": 1200000.0,
                "status": "active",
                "primary_contact": "Bruce Wayne (Executive Director)",
                "sla_tier": "platinum",
            },
            "CUST-103": {
                "customer_id": "CUST-103",
                "name": "Stark Industries",
                "domain": "starktech.com",
                "email": "it@starktech.com",
                "tier": "growth",
                "arr_usd": 75000.0,
                "status": "active",
                "primary_contact": "Tony Stark (CTO)",
                "sla_tier": "silver",
            },
        }

        self.tickets: Dict[str, Dict[str, Any]] = {
            "TCK-501": {
                "ticket_id": "TCK-501",
                "customer_id": "CUST-101",
                "title": "Database connection pool timeout in EU-West cluster",
                "status": "open",
                "priority": "high",
                "created_at": "2026-11-20T11:20:00Z",
                "notes": [
                    "Analyst identified connection starvation during peak ingestion.",
                ],
            },
            "TCK-502": {
                "ticket_id": "TCK-502",
                "customer_id": "CUST-102",
                "title": "SSO SAML Certificate rotation and OAuth renewal",
                "status": "in_progress",
                "priority": "medium",
                "created_at": "2026-11-22T08:00:00Z",
                "notes": [
                    "Security team dispatched new public cert bundle.",
                ],
            },
            "TCK-503": {
                "ticket_id": "TCK-503",
                "customer_id": "CUST-103",
                "title": "API Rate limit upgrade request for seasonal analytics",
                "status": "resolved",
                "priority": "low",
                "created_at": "2026-11-18T16:45:00Z",
                "notes": [
                    "Limit increased to 500 req/min for Q4.",
                ],
            },
        }

    def _check_outage(self) -> None:
        if self.simulate_outage:
            raise ConnectionError("CRM Service unavailable (simulated outage).")

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        self._check_outage()
        if customer_id in self.customers:
            return self.customers[customer_id]
        # Search by email or domain
        for cust in self.customers.values():
            if cust.get("email") == customer_id or cust.get("domain") == customer_id:
                return cust
        return None

    def search_customers(self, query: str) -> List[Dict[str, Any]]:
        self._check_outage()
        q = query.lower()
        return [
            c
            for c in self.customers.values()
            if q in c["name"].lower()
            or q in c["domain"].lower()
            or q in c["email"].lower()
        ]

    def get_tickets(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self._check_outage()
        results = list(self.tickets.values())
        if customer_id:
            results = [t for t in results if t.get("customer_id") == customer_id]
        if status:
            results = [t for t in results if t.get("status") == status.lower()]
        return results

    def update_ticket(
        self,
        ticket_id: str,
        status: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._check_outage()
        if ticket_id not in self.tickets:
            raise KeyError(f"Ticket '{ticket_id}' not found.")
        ticket = self.tickets[ticket_id]
        if status:
            ticket["status"] = status.lower()
        if note:
            ticket.setdefault("notes", []).append(note)
        ticket["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return ticket
