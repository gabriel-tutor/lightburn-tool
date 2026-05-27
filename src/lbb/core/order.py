"""Domain types for the order-aware workflow.

A real customer order may contain multiple line items (e.g. matching wallets
with different names). The PDF filename is the order number; each item
references a SKU + customization data + a design PDF path. The eventual
Supabase/Airtable backend will surface orders in this exact shape via the
`OrderRepository` Protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from lbb.core.models import Sku


@dataclass(frozen=True, slots=True)
class Customer:
    name: str
    email: str = ""


@dataclass(frozen=True, slots=True)
class OrderItem:
    """One line item — references a SKU and carries customer-specific data."""

    item_id: str
    sku: Sku
    customization: dict[str, str] = field(default_factory=dict)
    pdf_path: str = ""  # may be a bare filename (resolved relative to dropped PDF)
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Order:
    order_number: str
    customer: Customer
    items: tuple[OrderItem, ...]
    placed_at: datetime | None = None
    notes: str = ""
