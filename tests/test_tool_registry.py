"""Unit tests for ToolRegistry and FunctionalTool wrapping."""

import pytest

from lakenterprises.tools.base import (BaseTool, FunctionalTool, RiskLevel,
                                       ToolCategory)
from lakenterprises.tools.registry import ToolRegistry


class DummyEchoTool(BaseTool):
    name = "dummy_echo"
    description = "Echoes inputs back."
    category = ToolCategory.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_roles = ["viewer", "analyst", "manager", "admin"]

    def run(self, message: str) -> str:
        return f"echo: {message}"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }


def test_registry_register_and_get():
    reg = ToolRegistry()
    tool = DummyEchoTool()
    reg.register(tool)

    assert "dummy_echo" in reg
    assert len(reg) == 1
    assert reg.get("dummy_echo") is tool
    assert reg.get("nonexistent") is None


def test_registry_empty_name_raises():
    reg = ToolRegistry()

    class BadTool(BaseTool):
        name = ""
        description = "Bad"

        def run(self):
            pass

    with pytest.raises(ValueError, match="must not be empty"):
        reg.register(BadTool())


def test_registry_register_function():
    reg = ToolRegistry()

    def add(a: int, b: int) -> int:
        return a + b

    tool = reg.register_function(
        name="math_add",
        description="Add two numbers",
        func=add,
        category=ToolCategory.READ,
        risk_level=RiskLevel.LOW,
    )

    assert isinstance(tool, FunctionalTool)
    assert reg.get("math_add") is tool
    assert tool.run(a=3, b=7) == 10


def test_registry_list_and_filter():
    reg = ToolRegistry()
    reg.register(DummyEchoTool())
    reg.register_function(
        name="high_write",
        description="High risk write tool",
        func=lambda x: x,
        category=ToolCategory.WRITE,
        risk_level=RiskLevel.HIGH,
    )

    all_tools = reg.list_tools()
    assert len(all_tools) == 2

    reads = reg.list_tools(category=ToolCategory.READ)
    assert len(reads) == 1
    assert reads[0].name == "dummy_echo"

    writes = reg.list_tools(category=ToolCategory.WRITE)
    assert len(writes) == 1
    assert writes[0].name == "high_write"

    high_risks = reg.list_tools(risk_level=RiskLevel.HIGH)
    assert len(high_risks) == 1
    assert high_risks[0].name == "high_write"


def test_registry_get_schemas():
    reg = ToolRegistry()
    reg.register(DummyEchoTool())
    schemas = reg.get_schemas()
    assert len(schemas) == 1
    s = schemas[0]
    assert s["type"] == "function"
    assert s["function"]["name"] == "dummy_echo"
    assert s["category"] == "read"
    assert s["risk_level"] == "low"
    assert "parameters" in s["function"]


def test_registry_unregister_and_clear():
    reg = ToolRegistry()
    reg.register(DummyEchoTool())
    assert len(reg) == 1

    assert reg.unregister("dummy_echo") is True
    assert reg.unregister("dummy_echo") is False
    assert len(reg) == 0

    reg.register(DummyEchoTool())
    reg.clear()
    assert len(reg) == 0
