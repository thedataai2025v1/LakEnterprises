"""Unit and integration tests for read-only enterprise tools."""

import pytest

from lakenterprises.tools.read_only import (CRMCustomerLookupTool,
                                            CRMTicketLookupTool,
                                            DocumentSearchTool,
                                            ERPInventoryLookupTool,
                                            ERPOrderLookupTool,
                                            KnowledgeGraphLookupTool,
                                            ProcessStatusLookupTool)


def test_document_search_tool():
    tool = DocumentSearchTool()
    with pytest.raises(ValueError, match="cannot be empty"):
        tool.run(query="")

    results = tool.run(query="database connection pool", top_k=3)
    assert isinstance(results, list)
    schema = tool.get_parameters_schema()
    assert "query" in schema["properties"]


def test_crm_customer_lookup_tool():
    tool = CRMCustomerLookupTool()
    with pytest.raises(ValueError):
        tool.run(customer_id="")

    res = tool.run(customer_id="CUST-101")
    assert res["found"] is True
    assert res["customer"]["name"] == "Acme Global Industries"

    missing = tool.run(customer_id="NONEXISTENT")
    assert missing["found"] is False


def test_crm_ticket_lookup_tool():
    tool = CRMTicketLookupTool()
    tickets = tool.run(customer_id="CUST-101")
    assert len(tickets) >= 1
    assert tickets[0]["ticket_id"] == "TCK-501"

    filtered = tool.run(status="resolved")
    assert all(t["status"] == "resolved" for t in filtered)


def test_erp_order_lookup_tool():
    tool = ERPOrderLookupTool()
    with pytest.raises(ValueError):
        tool.run(order_id="")

    order = tool.run(order_id="PO-9001")
    assert order["found"] is True
    assert order["order"]["vendor_id"] == "VND-ACME"

    missing = tool.run(order_id="PO-MISSING")
    assert missing["found"] is False


def test_erp_inventory_lookup_tool():
    tool = ERPInventoryLookupTool()
    with pytest.raises(ValueError):
        tool.run(sku="")

    item = tool.run(sku="SKU-SRV-01")
    assert item["found"] is True
    assert item["inventory"]["in_stock"] == 14

    missing = tool.run(sku="UNKNOWN-SKU")
    assert missing["found"] is False


def test_process_status_lookup_tool():
    tool = ProcessStatusLookupTool()
    with pytest.raises(ValueError):
        tool.run(instance_id="")

    res = tool.run(instance_id="nonexistent-id")
    assert res["found"] is False


def test_knowledge_graph_lookup_tool():
    tool = KnowledgeGraphLookupTool()
    with pytest.raises(ValueError):
        tool.run(entity_id="")

    res = tool.run(entity_id="CUST-101")
    assert res["entity"] == "Acme Global Industries"
    assert len(res["relationships"]) >= 1
    rel_names = [r["rel"] for r in res["relationships"]]
    assert "USES_CLUSTER" in rel_names
