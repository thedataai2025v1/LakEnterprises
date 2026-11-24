"""Protocol definitions for enterprise integration adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class ERPAdapter(Protocol):
    """Protocol for interacting with Enterprise Resource Planning systems."""

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve purchase order or invoice by ID."""
        ...

    def get_vendor_orders(self, vendor_id: str) -> List[Dict[str, Any]]:
        """Retrieve all orders associated with a vendor."""
        ...

    def get_inventory(self, sku: str) -> Optional[Dict[str, Any]]:
        """Query inventory quantity and warehouse location for SKU."""
        ...

    def create_purchase_order(
        self,
        vendor_id: str,
        items: List[Dict[str, Any]],
        total_amount: float,
    ) -> Dict[str, Any]:
        """Create a new purchase order in the ERP."""
        ...


@runtime_checkable
class CRMAdapter(Protocol):
    """Protocol for interacting with Customer Relationship Management systems."""

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve customer profile by ID or email."""
        ...

    def search_customers(self, query: str) -> List[Dict[str, Any]]:
        """Search customers by name, domain, or email."""
        ...

    def get_tickets(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve support tickets optionally filtered by customer or status."""
        ...

    def update_ticket(
        self,
        ticket_id: str,
        status: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update ticket status and append notes."""
        ...


@runtime_checkable
class EmailAdapter(Protocol):
    """Protocol for transactional email and alerting dispatch."""

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Dispatch an email message."""
        ...

    def get_sent_emails(
        self,
        recipient: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve sent emails (for auditing and verification)."""
        ...

    def clear_outbox(self) -> None:
        """Clear the outbox store."""
        ...
