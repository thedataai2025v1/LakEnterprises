"""Base definitions, schemas, and abstract classes for agent tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolCategory(str, Enum):
    """Functional categories of tools."""

    READ = "read"
    WRITE = "write"
    ACTION = "action"


class RiskLevel(str, Enum):
    """Risk tiers for tool execution governance."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolResult(BaseModel):
    """Standardized result returned by tool execution."""

    success: bool = True
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    requires_approval: bool = False
    approval_request_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    """Metadata specification describing a registered tool."""

    name: str
    description: str
    category: ToolCategory = ToolCategory.READ
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    allowed_roles: List[str] = Field(
        default_factory=lambda: ["viewer", "analyst", "manager", "admin"]
    )
    parameters_schema: Dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base class for all agent tools."""

    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.READ
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    allowed_roles: List[str] = ["viewer", "analyst", "manager", "admin"]

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """Execute tool synchronously with provided kwargs."""
        pass

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Return JSON Schema for tool parameters."""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def get_definition(self) -> ToolDefinition:
        """Return the structured ToolDefinition metadata."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            category=self.category,
            risk_level=self.risk_level,
            requires_approval=self.requires_approval,
            allowed_roles=self.allowed_roles,
            parameters_schema=self.get_parameters_schema(),
        )


class FunctionalTool(BaseTool):
    """Tool wrapper for callable Python functions."""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        category: ToolCategory = ToolCategory.READ,
        risk_level: RiskLevel = RiskLevel.LOW,
        requires_approval: bool = False,
        allowed_roles: Optional[List[str]] = None,
        parameters_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.description = description
        self.func = func
        self.category = category
        self.risk_level = risk_level
        self.requires_approval = requires_approval
        self.allowed_roles = (
            allowed_roles
            if allowed_roles is not None
            else ["viewer", "analyst", "manager", "admin"]
        )
        self._parameters_schema = parameters_schema or {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def run(self, **kwargs: Any) -> Any:
        return self.func(**kwargs)

    def get_parameters_schema(self) -> Dict[str, Any]:
        return self._parameters_schema
