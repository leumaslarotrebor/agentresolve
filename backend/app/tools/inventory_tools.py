from __future__ import annotations

import logging

from pydantic import BaseModel, ValidationError

from app.services.data_store import get_store

logger = logging.getLogger("agentresolve.tools.inventory")


class CheckInventoryArgs(BaseModel):
    product_id: str
    quantity: int = 1


def check_inventory(args: dict) -> dict:
    """Check current inventory for a product against a requested quantity."""
    try:
        parsed = CheckInventoryArgs(**args)
    except ValidationError as e:
        return {"success": False, "error": f"invalid_arguments: {e}"}

    store = get_store()
    product = store.get_product(parsed.product_id)
    if product is None:
        logger.info("check_inventory: unknown product_id=%s", parsed.product_id)
        return {"success": False, "error": "product_not_found"}

    available = product.inventory >= parsed.quantity
    logger.info(
        "check_inventory: product=%s requested=%d in_stock=%d available=%s",
        parsed.product_id, parsed.quantity, product.inventory, available,
    )
    return {
        "success": True,
        "data": {
            "product_id": product.product_id,
            "name": product.name,
            "requested_quantity": parsed.quantity,
            "in_stock": product.inventory,
            "available": available,
            "replacement_eligible": product.replacement_eligible,
        },
    }
