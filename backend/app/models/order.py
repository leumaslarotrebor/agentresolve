from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel


class OrderStatus(str, Enum):
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class Order(BaseModel):
    order_id: str
    customer_id: str
    product_id: str
    order_date: date
    delivery_date: date | None = None
    status: OrderStatus
    price: float
    quantity: int = 1


class Product(BaseModel):
    product_id: str
    name: str
    category: str
    price: float
    inventory: int
    replacement_eligible: bool = True
