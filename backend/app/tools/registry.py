"""
Central registry of agent tools.

Each entry pairs a JSON-schema tool definition (in the shape the Anthropic
Messages API / OpenAI function-calling expects) with the Python callable
that implements it. The agent never hardcodes tool logic itself — it is
handed this registry and decides at runtime which tools to call.
"""
from __future__ import annotations

from typing import Any, Callable

from app.tools.action_tools import (
    create_refund,
    create_replacement,
    create_support_ticket,
    send_customer_message,
)
from app.tools.customer_tools import get_customer
from app.tools.inventory_tools import check_inventory
from app.tools.knowledge_tools import search_knowledge_base
from app.tools.order_tools import get_order

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_customer",
        "description": (
            "Look up a customer record by customer_id, email, or name. "
            "Use this first to identify who is making the request."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "email": {"type": "string"},
                "name": {"type": "string"},
            },
        },
    },
    {
        "name": "get_order",
        "description": (
            "Look up an order by order_id, or the most recent order for a "
            "customer_id. Use this to find what the customer purchased."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "customer_id": {"type": "string"},
            },
        },
    },
    {
        "name": "search_knowledge_base",
        "description": (
            "Search internal support policy documents (damaged product, "
            "refund, replacement, warranty, escalation, delivery policies). "
            "Use this before deciding on a resolution so the decision is "
            "grounded in actual policy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_inventory",
        "description": (
            "Check current stock for a product before promising a "
            "replacement. Returns available quantity and eligibility."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "quantity": {"type": "integer"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "create_replacement",
        "description": (
            "Create a replacement order for a damaged/defective item. Only "
            "call this after confirming eligibility, the replacement "
            "window, and inventory availability. Fails safely (does not "
            "fabricate success) if any condition is not met."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "reason": {"type": "string"},
                "idempotency_key": {"type": "string"},
            },
            "required": ["order_id", "reason"],
        },
    },
    {
        "name": "create_refund",
        "description": (
            "Issue a refund for an order. Refunds at or above the "
            "auto-approval threshold require human approval first "
            "(approved=true is only set by the system after approval)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount": {"type": "number"},
                "reason": {"type": "string"},
                "approved": {"type": "boolean"},
                "idempotency_key": {"type": "string"},
            },
            "required": ["order_id", "amount", "reason"],
        },
    },
    {
        "name": "create_support_ticket",
        "description": (
            "Escalate to a human support ticket — use when inventory is "
            "unavailable, the request is outside policy, the account is "
            "suspended, or you cannot confidently resolve the request."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "order_id": {"type": "string"},
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
                "idempotency_key": {"type": "string"},
            },
            "required": ["customer_id", "subject", "description"],
        },
    },
    {
        "name": "send_customer_message",
        "description": (
            "Send the final customer-facing message summarizing the "
            "resolution. Call this last, once a resolution has been "
            "reached (or a decision to escalate has been made)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "message": {"type": "string"},
                "channel": {"type": "string", "enum": ["email", "sms", "chat"]},
            },
            "required": ["customer_id", "message"],
        },
    },
]

TOOL_IMPLEMENTATIONS: dict[str, ToolFn] = {
    "get_customer": get_customer,
    "get_order": get_order,
    "search_knowledge_base": search_knowledge_base,
    "check_inventory": check_inventory,
    "create_replacement": create_replacement,
    "create_refund": create_refund,
    "create_support_ticket": create_support_ticket,
    "send_customer_message": send_customer_message,
}

# Actions that are consequential enough to require the human-approval
# workflow when they cross a risk threshold (checked in agent/planner.py).
HIGH_RISK_TOOLS = {"create_refund"}


def dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    fn = TOOL_IMPLEMENTATIONS.get(name)
    if fn is None:
        return {"success": False, "error": f"unknown_tool: {name}"}
    try:
        return fn(args)
    except Exception as exc:  # tool implementations validate their own
        # inputs, but this is the last line of defense against a tool
        # crashing the whole agent run.
        return {"success": False, "error": f"tool_execution_failed: {exc}"}
