"""Agent tools package: registry, policy engine, read-only and write tools."""

from __future__ import annotations

from typing import Optional

from lakenterprises.tools.base import (BaseTool, FunctionalTool, RiskLevel,
                                       ToolCategory, ToolDefinition,
                                       ToolResult)
from lakenterprises.tools.executor import ToolExecutor
from lakenterprises.tools.policy import PolicyDecision, ToolPolicyEngine
from lakenterprises.tools.read_only import (CRMCustomerLookupTool,
                                            CRMTicketLookupTool,
                                            DocumentSearchTool,
                                            ERPInventoryLookupTool,
                                            ERPOrderLookupTool,
                                            KnowledgeGraphLookupTool,
                                            ProcessStatusLookupTool)
from lakenterprises.tools.registry import ToolRegistry, default_registry
from lakenterprises.tools.write_tools import (ApprovalDecisionTool,
                                              CRMUpdateTicketTool,
                                              EmailDispatchTool,
                                              ERPCreatePurchaseOrderTool,
                                              ProcessTaskSubmitTool)


def register_default_tools(registry: Optional[ToolRegistry] = None) -> ToolRegistry:
    """Register all built-in enterprise read and write tools into the target registry."""
    reg = registry or default_registry

    # Read-only tools
    reg.register(DocumentSearchTool())
    reg.register(CRMCustomerLookupTool())
    reg.register(CRMTicketLookupTool())
    reg.register(ERPOrderLookupTool())
    reg.register(ERPInventoryLookupTool())
    reg.register(ProcessStatusLookupTool())
    reg.register(KnowledgeGraphLookupTool())

    # Write & Action tools
    reg.register(CRMUpdateTicketTool())
    reg.register(ERPCreatePurchaseOrderTool())
    reg.register(EmailDispatchTool())
    reg.register(ProcessTaskSubmitTool())
    reg.register(ApprovalDecisionTool())

    return reg


__all__ = [
    "BaseTool",
    "FunctionalTool",
    "ToolCategory",
    "RiskLevel",
    "ToolResult",
    "ToolDefinition",
    "ToolRegistry",
    "default_registry",
    "PolicyDecision",
    "ToolPolicyEngine",
    "ToolExecutor",
    "DocumentSearchTool",
    "CRMCustomerLookupTool",
    "CRMTicketLookupTool",
    "ERPOrderLookupTool",
    "ERPInventoryLookupTool",
    "ProcessStatusLookupTool",
    "KnowledgeGraphLookupTool",
    "CRMUpdateTicketTool",
    "ERPCreatePurchaseOrderTool",
    "EmailDispatchTool",
    "ProcessTaskSubmitTool",
    "ApprovalDecisionTool",
    "register_default_tools",
]
