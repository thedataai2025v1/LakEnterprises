"""Unit tests for MockERPAdapter, MockCRMAdapter, and MockEmailAdapter."""

import pytest

from lakenterprises.integrations import (MockCRMAdapter, MockEmailAdapter,
                                         MockERPAdapter)


class TestMockERPAdapter:
    def test_get_existing_order(self):
        erp = MockERPAdapter()
        order = erp.get_order("PO-9001")
        assert order is not None
        assert order["vendor_id"] == "VND-ACME"
        assert order["total_amount"] == 45000.00

    def test_get_missing_order(self):
        erp = MockERPAdapter()
        assert erp.get_order("PO-UNKNOWN") is None

    def test_get_vendor_orders(self):
        erp = MockERPAdapter()
        orders = erp.get_vendor_orders("VND-GLOBEX")
        assert len(orders) == 1
        assert orders[0]["order_id"] == "PO-9002"

    def test_get_inventory(self):
        erp = MockERPAdapter()
        item = erp.get_inventory("SKU-SRV-01")
        assert item is not None
        assert item["in_stock"] == 14
        assert item["warehouse"] == "US-EAST-DC1"

    def test_create_purchase_order(self):
        erp = MockERPAdapter()
        new_order = erp.create_purchase_order(
            vendor_id="VND-TEST",
            items=[{"sku": "SKU-TEST", "qty": 1, "price": 500.0}],
            total_amount=500.0,
        )
        assert new_order["order_id"].startswith("PO-")
        assert new_order["status"] == "pending_approval"
        assert erp.get_order(new_order["order_id"]) is not None

    def test_simulated_outage(self):
        erp = MockERPAdapter(simulate_outage=True)
        with pytest.raises(ConnectionError, match="unavailable"):
            erp.get_order("PO-9001")


class TestMockCRMAdapter:
    def test_get_customer_by_id(self):
        crm = MockCRMAdapter()
        cust = crm.get_customer("CUST-101")
        assert cust is not None
        assert cust["name"] == "Acme Global Industries"
        assert cust["tier"] == "enterprise"

    def test_get_customer_by_domain_and_email(self):
        crm = MockCRMAdapter()
        cust1 = crm.get_customer("waynecorp.com")
        assert cust1 is not None
        assert cust1["customer_id"] == "CUST-102"

        cust2 = crm.get_customer("it@starktech.com")
        assert cust2 is not None
        assert cust2["customer_id"] == "CUST-103"

    def test_search_customers(self):
        crm = MockCRMAdapter()
        results = crm.search_customers("wayne")
        assert len(results) == 1
        assert results[0]["customer_id"] == "CUST-102"

    def test_get_and_update_tickets(self):
        crm = MockCRMAdapter()
        tickets = crm.get_tickets(customer_id="CUST-101")
        assert len(tickets) == 1
        assert tickets[0]["ticket_id"] == "TCK-501"

        updated = crm.update_ticket(
            "TCK-501", status="resolved", note="Fixed pool timeout."
        )
        assert updated["status"] == "resolved"
        assert "Fixed pool timeout." in updated["notes"]

    def test_update_missing_ticket_raises(self):
        crm = MockCRMAdapter()
        with pytest.raises(KeyError):
            crm.update_ticket("NONEXISTENT", status="closed")

    def test_simulated_outage(self):
        crm = MockCRMAdapter(simulate_outage=True)
        with pytest.raises(ConnectionError, match="unavailable"):
            crm.get_customer("CUST-101")


class TestMockEmailAdapter:
    def test_send_and_retrieve_email(self):
        email_svc = MockEmailAdapter()
        msg = email_svc.send_email(
            to="test@example.com",
            subject="Alert: High Severity",
            body="Incident has been resolved.",
            cc=["admin@example.com"],
        )
        assert msg["message_id"].startswith("msg-")
        assert msg["to"] == "test@example.com"
        assert msg["status"] == "delivered"

        sent = email_svc.get_sent_emails()
        assert len(sent) == 1
        assert sent[0]["subject"] == "Alert: High Severity"

        filtered = email_svc.get_sent_emails("test@example.com")
        assert len(filtered) == 1

        email_svc.clear_outbox()
        assert len(email_svc.get_sent_emails()) == 0

    def test_simulated_outage(self):
        email_svc = MockEmailAdapter(simulate_outage=True)
        with pytest.raises(ConnectionError, match="unavailable"):
            email_svc.send_email(to="x@y.com", subject="a", body="b")
