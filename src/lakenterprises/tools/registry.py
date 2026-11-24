"""Central registry for discovering, registering, and inspecting agent tools."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from lakenterprises.tools.base import (BaseTool, FunctionalTool, RiskLevel,
                                       ToolCategory, ToolDefinition)

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Thread-safe registry of tools available to enterprise AI agents."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a BaseTool instance."""
        if not tool.name:
            raise ValueError("Tool name must not be empty.")
        if tool.name in self._tools:
            logger.info("Overwriting existing tool registration: %s", tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s (%s)", tool.name, tool.category.value)

    def register_function(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        category: ToolCategory = ToolCategory.READ,
        risk_level: RiskLevel = RiskLevel.LOW,
        requires_approval: bool = False,
        allowed_roles: Optional[List[str]] = None,
        parameters_schema: Optional[Dict[str, Any]] = None,
    ) -> FunctionalTool:
        """Helper to register a standalone Python function as a tool."""
        tool = FunctionalTool(
            name=name,
            description=description,
            func=func,
            category=category,
            risk_level=risk_level,
            requires_approval=requires_approval,
            allowed_roles=allowed_roles,
            parameters_schema=parameters_schema,
        )
        self.register(tool)
        return tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        risk_level: Optional[RiskLevel] = None,
    ) -> List[ToolDefinition]:
        """List definitions of registered tools with optional filtering."""
        results: List[ToolDefinition] = []
        for tool in self._tools.values():
            if category is not None and tool.category != category:
                continue
            if risk_level is not None and tool.risk_level != risk_level:
                continue
            results.append(tool.get_definition())
        return results

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Export tool definitions in OpenAI/LangChain function calling schema format."""
        schemas = []
        for tool in self._tools.values():
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.get_parameters_schema(),
                    },
                    "category": tool.category.value,
                    "risk_level": tool.risk_level.value,
                    "requires_approval": tool.requires_approval,
                }
            )
        return schemas

    def clear(self) -> None:
        """Reset and unregister all tools."""
        self._tools.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# Global default registry instance
default_registry = ToolRegistry()
