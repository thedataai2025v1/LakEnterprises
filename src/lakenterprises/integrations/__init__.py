"""Integrations package exporting protocols and mock enterprise adapters."""

from lakenterprises.integrations.base import (CRMAdapter, EmailAdapter,
                                              ERPAdapter)
from lakenterprises.integrations.mock_crm import MockCRMAdapter
from lakenterprises.integrations.mock_email import MockEmailAdapter
from lakenterprises.integrations.mock_erp import MockERPAdapter

__all__ = [
    "ERPAdapter",
    "CRMAdapter",
    "EmailAdapter",
    "MockERPAdapter",
    "MockCRMAdapter",
    "MockEmailAdapter",
]
