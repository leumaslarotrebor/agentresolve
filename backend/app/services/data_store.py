"""
Mock enterprise "system of record".

Loads customers/orders/products from local JSON at startup and serves them
in memory. This stands in for Salesforce / an order-management system /
inventory system in a real deployment (see README's production roadmap).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.config import settings
from app.models.customer import Customer
from app.models.order import Order, Product


class DataStore:
    """Thread-safe in-memory store with simple JSON-file persistence."""

    def __init__(self, data_dir: Path):
        self._lock = threading.Lock()
        self._data_dir = data_dir
        self.customers: dict[str, Customer] = {}
        self.orders: dict[str, Order] = {}
        self.products: dict[str, Product] = {}
        self.knowledge: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        with self._lock:
            customers_raw = _read_json(self._data_dir / "customers.json")
            orders_raw = _read_json(self._data_dir / "orders.json")
            products_raw = _read_json(self._data_dir / "products.json")
            knowledge_raw = _read_json(self._data_dir / "knowledge.json")

            self.customers = {c["customer_id"]: Customer(**c) for c in customers_raw}
            self.orders = {o["order_id"]: Order(**o) for o in orders_raw}
            self.products = {p["product_id"]: Product(**p) for p in products_raw}
            self.knowledge = knowledge_raw

    # --- read helpers -----------------------------------------------------
    def get_customer(self, customer_id: str) -> Customer | None:
        return self.customers.get(customer_id)

    def find_customer_by_email(self, email: str) -> Customer | None:
        email_lower = email.lower().strip()
        for c in self.customers.values():
            if c.email.lower() == email_lower:
                return c
        return None

    def find_customer_by_name(self, name: str) -> Customer | None:
        name_lower = name.lower().strip()
        for c in self.customers.values():
            if c.name.lower() == name_lower:
                return c
        return None

    def get_order(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)

    def get_orders_for_customer(self, customer_id: str) -> list[Order]:
        return [o for o in self.orders.values() if o.customer_id == customer_id]

    def get_product(self, product_id: str) -> Product | None:
        return self.products.get(product_id)

    # --- write helpers (mutate mock inventory / create records) ----------
    def decrement_inventory(self, product_id: str, quantity: int = 1) -> bool:
        with self._lock:
            product = self.products.get(product_id)
            if product is None or product.inventory < quantity:
                return False
            product.inventory -= quantity
            return True


_store: DataStore | None = None
_store_lock = threading.Lock()


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_store() -> DataStore:
    """Singleton accessor so tools/services share consistent mock state."""
    global _store
    with _store_lock:
        if _store is None:
            _store = DataStore(settings.data_dir)
        return _store


def reset_store() -> None:
    """Used by tests to get a fresh in-memory store between test cases."""
    global _store
    with _store_lock:
        _store = DataStore(settings.data_dir)
