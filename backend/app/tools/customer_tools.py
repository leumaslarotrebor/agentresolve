from __future__ import annotations

import logging

from pydantic import BaseModel, ValidationError

from app.services.data_store import get_store

logger = logging.getLogger("agentresolve.tools.customer")


class GetCustomerArgs(BaseModel):
    customer_id: str | None = None
    email: str | None = None
    name: str | None = None


def get_customer(args: dict) -> dict:
    """Look up a customer by id, email, or name in the mock CRM data.

    Returns {"success": True, "data": {...}} or
            {"success": False, "error": "..."} — never raises to the caller.
    """
    try:
        parsed = GetCustomerArgs(**args)
    except ValidationError as e:
        return {"success": False, "error": f"invalid_arguments: {e}"}

    if not any([parsed.customer_id, parsed.email, parsed.name]):
        return {
            "success": False,
            "error": "missing_identifier: provide customer_id, email, or name",
        }

    store = get_store()
    customer = None
    if parsed.customer_id:
        customer = store.get_customer(parsed.customer_id)
    elif parsed.email:
        customer = store.find_customer_by_email(parsed.email)
    elif parsed.name:
        customer = store.find_customer_by_name(parsed.name)

    if customer is None:
        logger.info("get_customer: not found for args=%s", parsed.model_dump())
        return {"success": False, "error": "customer_not_found"}

    logger.info("get_customer: found %s", customer.customer_id)
    return {"success": True, "data": customer.model_dump(mode="json")}
