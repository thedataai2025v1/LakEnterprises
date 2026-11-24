"""In-memory mock adapter for ERP systems (SAP / NetSuite / Dynamics)."""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional


class MockERPAdapter:
    """Mock ERP implementation providing orders, inventory, and vendor operations."""

    def __init__(self, simulate_outage: bool = False) -> None:
        self.simulate_outage = simulate_outage
        self.orders: Dict[str, Dict[str, Any]] = {
            "PO-9001": {
                "order_id": "PO-9001",
                "vendor_id": "VND-ACME",
                "vendor_name": "Acme Cloud Hardware Ltd",
                "status": "delivered",
                "total_amount": 45000.00,
                "currency": "USD",
                "items": [
                    {
                        "sku": "SKU-SRV-01",
                        "name": "Compute Rack Node 2U",
                        "qty": 5,
                        "price": 9000.00,
                    }
                ],
                "created_at": "2026-10-15T10:00:00Z",
            },
            "PO-9002": {
                "order_id": "PO-9002",
                "vendor_id": "VND-GLOBEX",
                "vendor_name": "Globex Networking Corp",
                "status": "pending_approval",
                "total_amount": 12500.00,
                "currency": "USD",
                "items": [
                    {
                        "sku": "SKU-SW-08",
                        "name": "48-Port 100GbE Switch",
                        "qty": 2,
                        "price": 6250.00,
                    }
                ],
                "created_at": "2026-11-01T14:30:00Z",
            },
            "PO-9003": {
                "order_id": "PO-9003",
                "vendor_id": "VND-INITECH",
                "vendor_name": "Initech Storage Solutions",
                "status": "approved",
                "total_amount": 8200.00,
                "currency": "USD",
                "items": [
                    {
                        "sku": "SKU-SSD-NVME",
                        "name": "NVMe 15TB Enterprise Storage",
                        "qty": 10,
                        "price": 820.00,
                    }
                ],
                "created_at": "2026-11-10T09:15:00Z",
            },
        }

        self.inventory: Dict[str, Dict[str, Any]] = {
            "SKU-SRV-01": {
                "sku": "SKU-SRV-01",
                "name": "Compute Rack Node 2U",
                "category": "Servers",
                "in_stock": 14,
                "reserved": 2,
                "warehouse": "US-EAST-DC1",
                "unit_cost": 9000.00,
            },
            "SKU-SW-08": {
                "sku": "SKU-SW-08",
                "name": "48-Port 100GbE Switch",
                "category": "Networking",
                "in_stock": 42,
                "reserved": 6,
                "warehouse": "US-WEST-DC2",
                "unit_cost": 6250.00,
            },
            "SKU-CAB-02": {
                "sku": "SKU-CAB-02",
                "name": "Fiber Optic LC-LC 10m",
                "category": "Cables",
                "in_stock": 350,
                "reserved": 20,
                "warehouse": "EU-CENTRAL-DC1",
                "unit_cost": 45.00,
            },
        }

    def _check_outage(self) -> None:
        if self.simulate_outage:
            raise ConnectionError("ERP Service unavailable (simulated outage).")

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        self._check_outage()
        return self.orders.get(order_id)

    def get_vendor_orders(self, vendor_id: str) -> List[Dict[str, Any]]:
        self._check_outage()
        return [
            order
            for order in self.orders.values()
            if order.get("vendor_id") == vendor_id
        ]

    def get_inventory(self, sku: str) -> Optional[Dict[str, Any]]:
        self._check_outage()
        return self.inventory.get(sku)

    def create_purchase_order(
        self,
        vendor_id: str,
        items: List[Dict[str, Any]],
        total_amount: float,
    ) -> Dict[str, Any]:
        self._check_outage()
        order_num = len(self.orders) + 9004
        order_id = f"PO-{order_num}"
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        new_order: Dict[str, Any] = {
            "order_id": order_id,
            "vendor_id": vendor_id,
            "vendor_name": f"Vendor {vendor_id}",
            "status": "pending_approval",
            "total_amount": float(total_amount),
            "currency": "USD",
            "items": items,
            "created_at": created_at,
        }
        self.orders[order_id] = new_order
        return new_order
