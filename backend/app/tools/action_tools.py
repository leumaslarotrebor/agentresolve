from __future__ import annotations

import logging
from datetime import date, timedelta

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.services import action_registry
from app.services.data_store import get_store

logger = logging.getLogger("agentresolve.tools.action")


# ---------------------------------------------------------------------------
# create_replacement
# ---------------------------------------------------------------------------
class CreateReplacementArgs(BaseModel):
    order_id: str
    reason: str
    idempotency_key: str | None = None


def create_replacement(args: dict) -> dict:
    """Create a replacement order for a damaged/defective item.

    Enforces: order exists, product is replacement_eligible, order was
    delivered within the replacement window, and inventory is available.
    Never fabricates success — every failure path returns a concrete reason.
    """
    try:
        parsed = CreateReplacementArgs(**args)
    except ValidationError as e:
        return {"success": False, "error": f"invalid_arguments: {e}"}

    existing = action_registry.get_existing(parsed.idempotency_key)
    if existing and existing.get("type") == "replacement":
        logger.info("create_replacement: idempotent hit for key=%s", parsed.idempotency_key)
        return {"success": True, "data": existing, "idempotent_replay": True}

    store = get_store()
    order = store.get_order(parsed.order_id)
    if order is None:
        return {"success": False, "error": "order_not_found"}

    product = store.get_product(order.product_id)
    if product is None:
        return {"success": False, "error": "product_not_found"}

    if not product.replacement_eligible:
        return {"success": False, "error": "product_not_replacement_eligible"}

    if order.delivery_date is None:
        return {"success": False, "error": "order_not_yet_delivered"}

    days_since_delivery = (date.today() - order.delivery_date).days
    if days_since_delivery > settings.replacement_window_days:
        return {
            "success": False,
            "error": "outside_replacement_window",
            "detail": f"delivered {days_since_delivery} days ago, "
                      f"window is {settings.replacement_window_days} days",
        }

    if product.inventory < order.quantity:
        return {
            "success": False,
            "error": "insufficient_inventory",
            "detail": f"requested {order.quantity}, in stock {product.inventory}",
        }

    ok = store.decrement_inventory(product.product_id, order.quantity)
    if not ok:
        return {"success": False, "error": "insufficient_inventory"}

    replacement_id = action_registry.next_replacement_id()
    eta = date.today() + timedelta(days=2)
    record = {
        "type": "replacement",
        "replacement_id": replacement_id,
        "order_id": order.order_id,
        "product_id": product.product_id,
        "reason": parsed.reason,
        "estimated_delivery": eta.isoformat(),
        "status": "created",
    }
    action_registry.register(parsed.idempotency_key, record)
    logger.info("create_replacement: created %s for order=%s", replacement_id, order.order_id)
    return {"success": True, "data": record}


# ---------------------------------------------------------------------------
# create_refund
# ---------------------------------------------------------------------------
class CreateRefundArgs(BaseModel):
    order_id: str
    amount: float
    reason: str
    approved: bool = False
    idempotency_key: str | None = None


def create_refund(args: dict) -> dict:
    """Issue a refund for an order.

    Refunds at/above the auto-approval threshold require `approved=True`
    (set only after the human-approval workflow completes) — this is a
    defense-in-depth check in addition to the agent-level approval gate.
    """
    try:
        parsed = CreateRefundArgs(**args)
    except ValidationError as e:
        return {"success": False, "error": f"invalid_arguments: {e}"}

    existing = action_registry.get_existing(parsed.idempotency_key)
    if existing and existing.get("type") == "refund":
        logger.info("create_refund: idempotent hit for key=%s", parsed.idempotency_key)
        return {"success": True, "data": existing, "idempotent_replay": True}

    store = get_store()
    order = store.get_order(parsed.order_id)
    if order is None:
        return {"success": False, "error": "order_not_found"}

    if order.delivery_date is not None:
        days_since_delivery = (date.today() - order.delivery_date).days
        if days_since_delivery > settings.refund_window_days:
            return {
                "success": False,
                "error": "outside_refund_window",
                "detail": f"delivered {days_since_delivery} days ago, "
                          f"window is {settings.refund_window_days} days",
            }

    if parsed.amount >= settings.refund_auto_approval_threshold_eur and not parsed.approved:
        return {
            "success": False,
            "error": "approval_required",
            "detail": f"amount {parsed.amount} >= threshold "
                      f"{settings.refund_auto_approval_threshold_eur}",
        }

    refund_id = action_registry.next_refund_id()
    record = {
        "type": "refund",
        "refund_id": refund_id,
        "order_id": order.order_id,
        "amount": parsed.amount,
        "reason": parsed.reason,
        "status": "issued",
    }
    action_registry.register(parsed.idempotency_key, record)
    logger.info("create_refund: issued %s amount=%.2f order=%s", refund_id, parsed.amount, order.order_id)
    return {"success": True, "data": record}


# ---------------------------------------------------------------------------
# create_support_ticket
# ---------------------------------------------------------------------------
class CreateSupportTicketArgs(BaseModel):
    customer_id: str
    subject: str
    description: str
    priority: str = "normal"
    order_id: str | None = None
    idempotency_key: str | None = None


def create_support_ticket(args: dict) -> dict:
    """Create a human-support escalation ticket."""
    try:
        parsed = CreateSupportTicketArgs(**args)
    except ValidationError as e:
        return {"success": False, "error": f"invalid_arguments: {e}"}

    existing = action_registry.get_existing(parsed.idempotency_key)
    if existing and existing.get("type") == "ticket":
        logger.info("create_support_ticket: idempotent hit for key=%s", parsed.idempotency_key)
        return {"success": True, "data": existing, "idempotent_replay": True}

    store = get_store()
    customer = store.get_customer(parsed.customer_id)
    if customer is None:
        return {"success": False, "error": "customer_not_found"}

    ticket_id = action_registry.next_ticket_id()
    record = {
        "type": "ticket",
        "ticket_id": ticket_id,
        "customer_id": parsed.customer_id,
        "order_id": parsed.order_id,
        "subject": parsed.subject,
        "description": parsed.description,
        "priority": parsed.priority,
        "status": "open",
    }
    action_registry.register(parsed.idempotency_key, record)
    logger.info("create_support_ticket: created %s for customer=%s", ticket_id, parsed.customer_id)
    return {"success": True, "data": record}


# ---------------------------------------------------------------------------
# send_customer_message
# ---------------------------------------------------------------------------
class SendCustomerMessageArgs(BaseModel):
    customer_id: str
    message: str
    channel: str = "email"


def send_customer_message(args: dict) -> dict:
    """Send (mock) the final customer-facing message."""
    try:
        parsed = SendCustomerMessageArgs(**args)
    except ValidationError as e:
        return {"success": False, "error": f"invalid_arguments: {e}"}

    store = get_store()
    customer = store.get_customer(parsed.customer_id)
    if customer is None:
        return {"success": False, "error": "customer_not_found"}

    message_id = action_registry.next_message_id()
    logger.info("send_customer_message: %s to customer=%s via %s", message_id, parsed.customer_id, parsed.channel)
    return {
        "success": True,
        "data": {
            "message_id": message_id,
            "customer_id": parsed.customer_id,
            "channel": parsed.channel,
            "message": parsed.message,
            "status": "sent",
        },
    }
