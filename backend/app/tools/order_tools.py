from __future__ import annotations

import logging

from pydantic import BaseModel, ValidationError

from app.services.data_store import get_store

logger = logging.getLogger("agentresolve.tools.order")


class GetOrderArgs(BaseModel):
    order_id: str | None = None
    customer_id: str | None = None


def get_order(args: dict) -> dict:
    """Look up an order by order_id, or the most recent order for a customer_id."""
    try:
        parsed = GetOrderArgs(**args)
    except ValidationError as e:
        return {"success": False, "error": f"invalid_arguments: {e}"}

    if not parsed.order_id and not parsed.customer_id:
        return {
            "success": False,
            "error": "missing_identifier: provide order_id or customer_id",
        }

    store = get_store()

    if parsed.order_id:
        order = store.get_order(parsed.order_id)
        if order is None:
            logger.info("get_order: not found order_id=%s", parsed.order_id)
            return {"success": False, "error": "order_not_found"}
        return {"success": True, "data": order.model_dump(mode="json")}

    orders = store.get_orders_for_customer(parsed.customer_id)
    if not orders:
        logger.info("get_order: no orders for customer_id=%s", parsed.customer_id)
        return {"success": False, "error": "no_orders_for_customer"}

    most_recent = max(orders, key=lambda o: o.order_date)
    return {
        "success": True,
        "data": most_recent.model_dump(mode="json"),
        "all_orders": [o.order_id for o in orders],
    }
