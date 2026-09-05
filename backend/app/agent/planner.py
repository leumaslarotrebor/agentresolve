"""
SimulatedPlanner: a deterministic implementation of the LLMClient interface.

This exists so AgentResolve is fully runnable and testable without an
Anthropic API key: set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to
switch to genuine model-driven tool selection (see llm_client.py). The
planner still goes through the exact same tool registry, validation,
business-rule enforcement, and approval workflow as the real LLM path —
only *which tool to call next* is decided by rules here instead of by a
model, so the rest of the architecture (and the tests) exercise the real
agent pipeline either way.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.agent.llm_client import LLMClient, LLMDecision
from app.agent.state import AgentState
from app.config import settings

_STEP_COUNTER_KEY = "_sim_step"


def classify_intent(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("refund", "money back", "reimburse")):
        return "refund"
    if any(k in t for k in ("damaged", "broken", "defective", "arrived damaged", "cracked")):
        return "damaged_product"
    if any(k in t for k in ("replace", "replacement")):
        return "damaged_product"
    if any(k in t for k in ("warranty",)):
        return "warranty"
    return "general_inquiry"


def classify_priority(text: str, customer: dict[str, Any] | None) -> str:
    t = text.lower()
    if any(k in t for k in ("urgent", "asap", "immediately", "before friday", "deadline")):
        return "high"
    if customer and customer.get("customer_tier") == "gold":
        return "medium-high"
    return "medium"


def _attempted(state: AgentState, tool: str) -> bool:
    return any(tc.tool == tool for tc in state.tool_calls)


def _last_result(state: AgentState, tool: str) -> dict[str, Any] | None:
    for tc in reversed(state.tool_calls):
        if tc.tool == tool:
            return tc.result
    return None


def _call(tool: str, args: dict[str, Any], state: AgentState) -> LLMDecision:
    state.context[_STEP_COUNTER_KEY] = state.context.get(_STEP_COUNTER_KEY, 0) + 1
    return LLMDecision(
        kind="tool_call",
        tool_name=tool,
        tool_args=args,
        tool_use_id=f"sim-{state.context[_STEP_COUNTER_KEY]}",
    )


class SimulatedPlanner(LLMClient):
    def decide_next_step(self, state: AgentState) -> LLMDecision:  # noqa: C901
        ctx = state.context
        request = state.customer_request

        if "intent" not in ctx:
            ctx["intent"] = classify_intent(request)

        intent = ctx["intent"]

        # 1. Identify the customer.
        if not _attempted(state, "get_customer"):
            args: dict[str, Any] = {}
            if ctx.get("customer_id_hint"):
                args["customer_id"] = ctx["customer_id_hint"]
            elif ctx.get("email_hint"):
                args["email"] = ctx["email_hint"]
            if not args:
                return LLMDecision(
                    kind="final",
                    text=(
                        "I wasn't able to identify your account from the details "
                        "provided. Please contact support with your customer ID "
                        "or the email used for your order."
                    ),
                )
            return _call("get_customer", args, state)

        customer_result = _last_result(state, "get_customer")
        if not customer_result or not customer_result.get("success"):
            return LLMDecision(
                kind="final",
                text=(
                    "We couldn't verify your account from the details provided. "
                    "Please contact support with your order number so we can help."
                ),
            )

        customer = ctx["customer"]
        ctx["priority"] = classify_priority(request, customer)

        if customer.get("account_status") == "suspended":
            if not _attempted(state, "create_support_ticket"):
                return _call(
                    "create_support_ticket",
                    {
                        "customer_id": customer["customer_id"],
                        "subject": "Suspended account requesting support",
                        "description": request,
                        "priority": "high",
                        "idempotency_key": ctx.get("idempotency_key"),
                    },
                    state,
                )
            if not _attempted(state, "send_customer_message"):
                return _call(
                    "send_customer_message",
                    {
                        "customer_id": customer["customer_id"],
                        "message": (
                            "Your account is currently suspended, so I'm unable to "
                            "process this automatically. I've created a support "
                            "ticket and a specialist will reach out shortly."
                        ),
                    },
                    state,
                )
            return LLMDecision(
                kind="final",
                text="Account suspended — escalated to a human support ticket rather than acting autonomously.",
            )

        # 2. Retrieve the order.
        if not _attempted(state, "get_order"):
            args = {}
            if ctx.get("order_id_hint"):
                args["order_id"] = ctx["order_id_hint"]
            else:
                args["customer_id"] = customer["customer_id"]
            return _call("get_order", args, state)

        order_result = _last_result(state, "get_order")
        if not order_result or not order_result.get("success"):
            if not _attempted(state, "send_customer_message"):
                return _call(
                    "send_customer_message",
                    {
                        "customer_id": customer["customer_id"],
                        "message": (
                            f"Hi {customer['name']}, I couldn't find an order matching "
                            "the details provided. Could you confirm your order number "
                            "and I'll look into this right away?"
                        ),
                    },
                    state,
                )
            return LLMDecision(
                kind="final",
                text="No matching order found — asked the customer to confirm their order number.",
            )

        order = ctx["order"]

        # 3. Ground the decision in policy.
        if not _attempted(state, "search_knowledge_base"):
            query = {
                "damaged_product": "damaged product replacement policy",
                "refund": "refund policy",
                "warranty": "warranty policy",
            }.get(intent, "escalation policy")
            return _call("search_knowledge_base", {"query": query}, state)

        # 4. Resolve by intent.
        if intent == "damaged_product":
            return self._resolve_damaged_product(state, customer, order)
        if intent == "refund":
            return self._resolve_refund(state, customer, order)
        if intent == "warranty":
            return self._resolve_warranty(state, customer, order)
        return self._resolve_general_inquiry(state, customer, order)

    # -- intent-specific resolution branches -------------------------------
    def _resolve_damaged_product(self, state: AgentState, customer: dict, order: dict) -> LLMDecision:
        ctx = state.context

        if not _attempted(state, "check_inventory"):
            return _call(
                "check_inventory",
                {"product_id": order["product_id"], "quantity": order.get("quantity", 1)},
                state,
            )

        inv_result = _last_result(state, "check_inventory")
        inv_available = bool(
            inv_result and inv_result.get("success") and inv_result["data"]["available"]
            and inv_result["data"]["replacement_eligible"]
        )

        action_tools = ("create_replacement", "create_support_ticket")
        if not any(_attempted(state, t) for t in action_tools):
            if inv_available:
                return _call(
                    "create_replacement",
                    {
                        "order_id": order["order_id"],
                        "reason": state.customer_request,
                        "idempotency_key": ctx.get("idempotency_key"),
                    },
                    state,
                )
            reason = "inventory unavailable" if inv_result and inv_result.get("success") else "eligibility check failed"
            return _call(
                "create_support_ticket",
                {
                    "customer_id": customer["customer_id"],
                    "order_id": order["order_id"],
                    "subject": f"Replacement needed — {reason}",
                    "description": state.customer_request,
                    "priority": "high",
                    "idempotency_key": ctx.get("idempotency_key"),
                },
                state,
            )

        return self._finalize(state, customer)

    def _resolve_refund(self, state: AgentState, customer: dict, order: dict) -> LLMDecision:
        ctx = state.context
        amount = ctx.get("explicit_amount") or order["price"] * order.get("quantity", 1)
        ctx["refund_amount"] = amount

        if order.get("delivery_date") and not ctx.get("_window_checked"):
            ctx["_window_checked"] = True
            delivered = date.fromisoformat(order["delivery_date"])
            days_since = (date.today() - delivered).days
            if days_since > settings.refund_window_days:
                ctx["refund_window_expired"] = True

        if ctx.get("refund_window_expired"):
            return self._finalize(state, customer)

        if ctx.get("refund_rejected"):
            if not _attempted(state, "create_support_ticket"):
                return _call(
                    "create_support_ticket",
                    {
                        "customer_id": customer["customer_id"],
                        "order_id": order["order_id"],
                        "subject": "High-value refund rejected — needs manual follow-up",
                        "description": state.customer_request,
                        "priority": "high",
                        "idempotency_key": ctx.get("idempotency_key"),
                    },
                    state,
                )
            return self._finalize(state, customer)

        if not _attempted(state, "create_refund"):
            approved = bool(ctx.get("human_approved"))
            if amount >= settings.refund_auto_approval_threshold_eur and not approved:
                return LLMDecision(
                    kind="request_approval",
                    tool_name="create_refund",
                    tool_args={
                        "order_id": order["order_id"],
                        "amount": amount,
                        "reason": state.customer_request,
                        "approved": True,
                        "idempotency_key": ctx.get("idempotency_key"),
                    },
                    text=(
                        f"Refund of EUR {amount:.2f} meets or exceeds the "
                        f"EUR {settings.refund_auto_approval_threshold_eur:.0f} autonomous "
                        "approval threshold and requires human sign-off."
                    ),
                )
            return _call(
                "create_refund",
                {
                    "order_id": order["order_id"],
                    "amount": amount,
                    "reason": state.customer_request,
                    "approved": approved,
                    "idempotency_key": ctx.get("idempotency_key"),
                },
                state,
            )

        refund_result = _last_result(state, "create_refund")
        if refund_result and not refund_result.get("success") and not _attempted(state, "create_support_ticket"):
            if refund_result.get("error") == "outside_refund_window":
                return self._finalize(state, customer)
            return _call(
                "create_support_ticket",
                {
                    "customer_id": customer["customer_id"],
                    "order_id": order["order_id"],
                    "subject": "Refund could not be processed automatically",
                    "description": f"{state.customer_request} | reason: {refund_result.get('error')}",
                    "priority": "high",
                    "idempotency_key": ctx.get("idempotency_key"),
                },
                state,
            )

        return self._finalize(state, customer)

    def _resolve_warranty(self, state: AgentState, customer: dict, order: dict) -> LLMDecision:
        ctx = state.context
        if not _attempted(state, "create_support_ticket"):
            return _call(
                "create_support_ticket",
                {
                    "customer_id": customer["customer_id"],
                    "order_id": order["order_id"],
                    "subject": "Warranty claim",
                    "description": state.customer_request,
                    "priority": "normal",
                    "idempotency_key": ctx.get("idempotency_key"),
                },
                state,
            )
        return self._finalize(state, customer)

    def _resolve_general_inquiry(self, state: AgentState, customer: dict, order: dict) -> LLMDecision:
        ctx = state.context
        if not _attempted(state, "create_support_ticket"):
            return _call(
                "create_support_ticket",
                {
                    "customer_id": customer["customer_id"],
                    "order_id": order.get("order_id"),
                    "subject": "General support inquiry",
                    "description": state.customer_request,
                    "priority": "normal",
                    "idempotency_key": ctx.get("idempotency_key"),
                },
                state,
            )
        return self._finalize(state, customer)

    def _finalize(self, state: AgentState, customer: dict) -> LLMDecision:
        if not _attempted(state, "send_customer_message"):
            message = _compose_customer_message(state, customer)
            return _call(
                "send_customer_message",
                {"customer_id": customer["customer_id"], "message": message},
                state,
            )
        return LLMDecision(kind="final", text=_compose_decision_summary(state))


def _compose_customer_message(state: AgentState, customer: dict) -> str:
    ctx = state.context
    action = ctx.get("action")
    name = customer["name"].split()[0]

    if action and action.get("type") == "replacement":
        return (
            f"Hi {name}, sorry about the damaged item. I've arranged a free "
            f"replacement (order {action['replacement_id']}), estimated to arrive by "
            f"{action.get('estimated_delivery')}. No further action is needed on your end."
        )
    if action and action.get("type") == "refund":
        return (
            f"Hi {name}, I've processed a refund of EUR {action['amount']:.2f} "
            f"(reference {action['refund_id']}) to your original payment method. "
            "You should see it within 3-5 business days."
        )
    if action and action.get("type") == "ticket":
        return (
            f"Hi {name}, thanks for flagging this. I've opened support ticket "
            f"{action['ticket_id']} and a specialist will follow up with you shortly "
            "with the next steps."
        )

    if ctx.get("refund_window_expired"):
        return (
            f"Hi {name}, I looked into this but the refund window for this order has "
            f"passed ({settings.refund_window_days} days from delivery), so I'm unable "
            "to process a refund automatically. Please contact support if you believe "
            "this qualifies for a manual exception."
        )

    refund_result = _last_result(state, "create_refund")
    if refund_result and not refund_result.get("success"):
        return (
            f"Hi {name}, I looked into this but the refund window has passed for this "
            "order, so I'm unable to process a refund automatically. Please reach out "
            "to support if you believe this is an exception."
        )

    return (
        f"Hi {name}, thanks for reaching out. I've reviewed your request and a member "
        "of our team will follow up with you shortly."
    )


def _compose_decision_summary(state: AgentState) -> str:
    ctx = state.context
    action = ctx.get("action")
    if action and action.get("type") == "replacement":
        return (
            "Decision: Replacement approved because the order is within the "
            "replacement window, the product is eligible, and inventory was available."
        )
    if action and action.get("type") == "refund":
        return "Decision: Refund issued because the request was within policy and, if applicable, human-approved."
    if action and action.get("type") == "ticket":
        return "Decision: Escalated to a human support ticket because the request could not be safely resolved autonomously."
    if ctx.get("refund_window_expired"):
        return "Decision: No refund issued — order falls outside the refund eligibility window."
    refund_result = _last_result(state, "create_refund")
    if refund_result and not refund_result.get("success"):
        return f"Decision: No refund issued — {refund_result.get('error')}."
    return "Decision: Reviewed the request; no autonomous action was applicable."
