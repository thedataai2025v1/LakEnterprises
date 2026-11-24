"""Read-only enterprise inspection and lookup tools for agents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lakenterprises.integrations.base import CRMAdapter, ERPAdapter
from lakenterprises.integrations.mock_crm import MockCRMAdapter
from lakenterprises.integrations.mock_erp import MockERPAdapter
from lakenterprises.services.document import DocumentService
from lakenterprises.services.process import ProcessService
from lakenterprises.tools.base import BaseTool, RiskLevel, ToolCategory


class DocumentSearchTool(BaseTool):
    """Searches indexed enterprise documentation and incident reports."""

    name = "document_search"
    description = (
        "Search indexed enterprise knowledge base, policy docs, and incident reports."
    )
    category = ToolCategory.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_roles = ["viewer", "analyst", "manager", "admin"]

    def __init__(self, document_service: Optional[DocumentService] = None) -> None:
        self.document_service = document_service or DocumentService()

    def run(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty.")
        results = self.document_service.search(query=query.strip(), top_k=top_k)
        return results

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query or keywords.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of search results to return.",
                    "default": 5,
                },
            },
            "required": ["query"],
        }


class CRMCustomerLookupTool(BaseTool):
    """Retrieves customer account profile, SLA tier, and ARR from CRM."""

    name = "crm_customer_lookup"
    description = "Look up customer account, SLA tier, primary contact, and ARR by customer ID or email."
    category = ToolCategory.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_roles = ["viewer", "analyst", "manager", "admin"]

    def __init__(self, crm_adapter: Optional[CRMAdapter] = None) -> None:
        self.crm_adapter = crm_adapter or MockCRMAdapter()

    def run(self, customer_id: str) -> Dict[str, Any]:
        if not customer_id:
            raise ValueError("customer_id is required.")
        cust = self.crm_adapter.get_customer(customer_id)
        if not cust:
            return {"found": False, "customer_id": customer_id}
        return {"found": True, "customer": cust}

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Unique customer ID (e.g. CUST-101) or company domain.",
                }
            },
            "required": ["customer_id"],
        }


class CRMTicketLookupTool(BaseTool):
    """Queries support tickets by customer ID or status."""

    name = "crm_ticket_lookup"
    description = "Query customer support tickets by customer ID or ticket status."
    category = ToolCategory.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_roles = ["viewer", "analyst", "manager", "admin"]

    def __init__(self, crm_adapter: Optional[CRMAdapter] = None) -> None:
        self.crm_adapter = crm_adapter or MockCRMAdapter()

    def run(
        self, customer_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return self.crm_adapter.get_tickets(customer_id=customer_id, status=status)

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Optional customer ID to filter tickets.",
                },
                "status": {
                    "type": "string",
                    "description": "Optional ticket status filter ('open', 'in_progress', 'resolved').",
                },
            },
            "required": [],
        }


class ERPOrderLookupTool(BaseTool):
    """Retrieves purchase order details from ERP."""

    name = "erp_order_lookup"
    description = (
        "Retrieve purchase order status, vendor info, and ordered items by order ID."
    )
    category = ToolCategory.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_roles = ["viewer", "analyst", "manager", "admin"]

    def __init__(self, erp_adapter: Optional[ERPAdapter] = None) -> None:
        self.erp_adapter = erp_adapter or MockERPAdapter()

    def run(self, order_id: str) -> Dict[str, Any]:
        if not order_id:
            raise ValueError("order_id is required.")
        order = self.erp_adapter.get_order(order_id)
        if not order:
            return {"found": False, "order_id": order_id}
        return {"found": True, "order": order}

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Purchase order identifier (e.g. PO-9001).",
                }
            },
            "required": ["order_id"],
        }


class ERPInventoryLookupTool(BaseTool):
    """Queries inventory warehouse levels for SKUs."""

    name = "erp_inventory_lookup"
    description = (
        "Check real-time warehouse stock level and reservation for an item SKU."
    )
    category = ToolCategory.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_roles = ["viewer", "analyst", "manager", "admin"]

    def __init__(self, erp_adapter: Optional[ERPAdapter] = None) -> None:
        self.erp_adapter = erp_adapter or MockERPAdapter()

    def run(self, sku: str) -> Dict[str, Any]:
        if not sku:
            raise ValueError("sku is required.")
        item = self.erp_adapter.get_inventory(sku)
        if not item:
            return {"found": False, "sku": sku}
        return {"found": True, "inventory": item}

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "Stock keeping unit identifier (e.g. SKU-SRV-01).",
                }
            },
            "required": ["sku"],
        }


class ProcessStatusLookupTool(BaseTool):
    """Inspects the live state of an enterprise process workflow."""

    name = "process_status_lookup"
    description = "Inspect the live status, tasks, and state machine progress of a process instance."
    category = ToolCategory.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_roles = ["viewer", "analyst", "manager", "admin"]

    def __init__(self, process_service: Optional[ProcessService] = None) -> None:
        self.process_service = process_service or ProcessService()

    def run(self, instance_id: str) -> Dict[str, Any]:
        if not instance_id:
            raise ValueError("instance_id is required.")
        instance = self.process_service.get_instance(instance_id)
        if not instance:
            return {"found": False, "instance_id": instance_id}
        tasks = self.process_service.list_tasks(instance_id)
        return {
            "found": True,
            "instance": instance,
            "tasks": tasks,
        }

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "instance_id": {
                    "type": "string",
                    "description": "Process instance identifier.",
                }
            },
            "required": ["instance_id"],
        }


class KnowledgeGraphLookupTool(BaseTool):
    """Queries knowledge graph relationships and entity connections."""

    name = "knowledge_graph_lookup"
    description = "Lookup graph entity relationships, dependencies, and linked systems."
    category = ToolCategory.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_roles = ["viewer", "analyst", "manager", "admin"]

    def run(self, entity_id: str) -> Dict[str, Any]:
        if not entity_id:
            raise ValueError("entity_id is required.")
        # Deterministic offline knowledge graph relationships
        entity_map = {
            "CUST-101": {
                "entity": "Acme Global Industries",
                "relationships": [
                    {"rel": "USES_CLUSTER", "target": "EU-West-Cluster-02"},
                    {"rel": "HAS_SLA", "target": "Gold-Tier-SLA"},
                    {"rel": "ASSOCIATED_INCIDENT", "target": "INC-2026-99"},
                ],
            },
            "EU-West-Cluster-02": {
                "entity": "EU-West Database Cluster",
                "relationships": [
                    {"rel": "DEPLOYED_IN", "target": "eu-west-1"},
                    {"rel": "DEPENDS_ON", "target": "PostgreSQL-Pool-Master"},
                ],
            },
        }
        res = entity_map.get(
            entity_id,
            {
                "entity": entity_id,
                "relationships": [],
            },
        )
        return {"entity_id": entity_id, **res}

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Identifier of the entity to traverse in the graph.",
                }
            },
            "required": ["entity_id"],
        }
