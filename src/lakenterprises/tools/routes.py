"""FastAPI routes for tool discovery, inspection, and execution."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from lakenterprises.auth.middleware import get_current_user
from lakenterprises.tools import (RiskLevel, ToolCategory, ToolDefinition,
                                  ToolExecutor, ToolResult,
                                  default_registry, register_default_tools)

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])

# Ensure default tools are registered
register_default_tools(default_registry)
_executor = ToolExecutor(registry=default_registry)


class ExecuteToolRequest(BaseModel):
    """Payload to execute an agent tool."""

    parameters: Dict[str, Any] = Field(default_factory=dict)
    approval_id: Optional[str] = None


@router.get("", response_model=List[ToolDefinition])
def list_tools(
    category: Optional[ToolCategory] = Query(None, description="Filter by category"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    _user: Dict[str, Any] = Depends(get_current_user),
) -> List[ToolDefinition]:
    """List all registered agent tools with schemas and governance metadata."""
    return default_registry.list_tools(category=category, risk_level=risk_level)


@router.get("/schemas")
def get_tool_schemas(
    _user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Export tool schemas formatted for LLM function calling."""
    return default_registry.get_schemas()


@router.get("/{name}", response_model=ToolDefinition)
def get_tool(
    name: str,
    _user: Dict[str, Any] = Depends(get_current_user),
) -> ToolDefinition:
    """Retrieve detailed specification and parameter schema for a specific tool."""
    tool = default_registry.get(name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{name}' was not found.",
        )
    return tool.get_definition()


@router.post("/{name}/execute", response_model=ToolResult)
def execute_tool(
    name: str,
    req: ExecuteToolRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> ToolResult:
    """Execute an agent tool under security policy and approval gating."""
    user_roles = current_user.get("roles", ["viewer"])
    user_id = current_user.get("user_id", "anonymous")

    result = _executor.execute(
        tool_name=name,
        parameters=req.parameters,
        user_roles=user_roles,
        user_id=user_id,
        approval_id=req.approval_id,
    )

    if not result.success and not result.requires_approval:
        if (
            "not registered" in (result.error or "").lower()
            or "not found" in (result.error or "").lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.error,
            )
        elif (
            "not authorized" in (result.error or "").lower()
            or "restricted" in (result.error or "").lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.error,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error,
            )

    return result
