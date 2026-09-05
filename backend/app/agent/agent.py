"""
Agent orchestrator.

Owns the run loop: repeatedly asks the LLMClient what to do next, executes
the chosen tool through the shared registry (with validation, idempotency,
and business-rule enforcement living in the tools themselves), records an
execution step + audit event for each action, and pauses for human approval
on high-risk actions instead of ever "just doing it".
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone

from app.agent.llm_client import LLMClient, LLMClientError, get_llm_client
from app.agent.planner import classify_priority
from app.agent.state import AgentState
from app.config import settings
from app.models.agent import (
    AgentAnalysis,
    AgentRunRequest,
    AgentRunResult,
    ApprovalDecisionRequest,
    ApprovalRequest,
    ApprovalStatus,
    ExecutionStep,
    RunStatus,
    StepStatus,
)
from app.services import audit_service
from app.tools.registry import dispatch_tool

logger = logging.getLogger("agentresolve.agent")

STEP_LABELS: dict[str, str] = {
    "get_customer": "Customer identified",
    "get_order": "Order retrieved",
    "search_knowledge_base": "Support policy retrieved",
    "check_inventory": "Inventory checked",
    "create_replacement": "Replacement created",
    "create_refund": "Refund processed",
    "create_support_ticket": "Support ticket created",
    "send_customer_message": "Customer notification prepared",
}

_states_lock = threading.Lock()
_active_states: dict[str, AgentState] = {}


class Agent:
    def __init__(self, llm_client: LLMClient | None = None):
        self._llm_client = llm_client or get_llm_client()

    # -- public API ----------------------------------------------------
    def run(self, request: AgentRunRequest) -> AgentRunResult:
        idem_key = request.idempotency_key
        if idem_key:
            candidate_run_id = f"RUN-{uuid.uuid4().hex[:10]}"
            existing_run_id = audit_service.register_idempotency_key(idem_key, candidate_run_id)
            if existing_run_id:
                existing = audit_service.get_run(existing_run_id)
                if existing:
                    logger.info("run: idempotent replay of run_id=%s", existing_run_id)
                    return existing
            run_id = candidate_run_id
        else:
            run_id = f"RUN-{uuid.uuid4().hex[:10]}"

        state = AgentState(run_id=run_id, customer_request=request.customer_request)
        state.context["customer_id_hint"] = request.customer_id
        state.context["order_id_hint"] = request.order_id
        state.context["idempotency_key"] = idem_key

        result = AgentRunResult(run_id=run_id, status=RunStatus.RUNNING)
        audit_service.save_run(result)
        self._record_step(
            result, "Request classified", tool=None, status=StepStatus.SUCCESS,
            summary=f"Customer message received ({len(request.customer_request)} chars).",
        )

        return self._advance(state, result)

    def submit_approval_decision(
        self, approval_id: str, decision: ApprovalDecisionRequest, approved: bool
    ) -> AgentRunResult:
        approval = audit_service.get_approval(approval_id)
        if approval is None:
            raise KeyError("approval_not_found")
        if approval.status != ApprovalStatus.PENDING:
            existing = audit_service.get_run(approval.run_id)
            if existing:
                return existing
            raise KeyError("run_not_found")

        approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        approval.resolved_at = datetime.now(timezone.utc)
        audit_service.save_approval(approval)

        with _states_lock:
            state = _active_states.pop(approval.run_id, None)
        result = audit_service.get_run(approval.run_id)
        if state is None or result is None:
            raise KeyError("run_not_found")

        result.pending_approval = approval
        audit_service.append_audit_event(
            result.run_id,
            {"event": "approval_decision", "approval_id": approval_id, "approved": approved,
             "decided_by": decision.decided_by, "note": decision.note},
        )

        if not approved:
            self._record_step(
                result, "Human approval rejected", tool=None, status=StepStatus.FAILED,
                summary=f"{approval.action} was rejected by {decision.decided_by}.",
            )
            state.context["human_approved"] = False
            state.context["refund_rejected"] = True
            result.status = RunStatus.RUNNING
            return self._advance(state, result)

        self._record_step(
            result, "Human approval granted", tool=None, status=StepStatus.SUCCESS,
            summary=f"{approval.action} approved by {decision.decided_by}.",
        )
        state.context["human_approved"] = True
        result.status = RunStatus.RUNNING
        return self._advance(state, result)

    # -- internals -------------------------------------------------------
    def _advance(self, state: AgentState, result: AgentRunResult) -> AgentRunResult:
        iterations = 0
        while iterations < settings.llm_max_tool_iterations:
            iterations += 1
            try:
                decision = self._llm_client.decide_next_step(state)
            except LLMClientError as exc:
                logger.error("run %s: LLM call failed: %s", state.run_id, exc)
                self._record_step(
                    result, "Agent reasoning failed", tool=None, status=StepStatus.FAILED,
                    summary="The reasoning service could not be reached.", error=str(exc),
                )
                result.status = RunStatus.FAILED
                result.error = str(exc)
                audit_service.save_run(result)
                return result

            if decision.kind == "request_approval":
                approval = ApprovalRequest(
                    approval_id=f"APR-{uuid.uuid4().hex[:8]}",
                    run_id=state.run_id,
                    action=decision.text or f"Execute {decision.tool_name}",
                    tool_name=decision.tool_name or "",
                    tool_args=decision.tool_args or {},
                    reason=decision.text or "Exceeds autonomous action threshold.",
                )
                audit_service.save_approval(approval)
                with _states_lock:
                    _active_states[state.run_id] = state
                self._record_step(
                    result, "Human approval requested", tool=decision.tool_name,
                    status=StepStatus.PENDING_APPROVAL, summary=approval.reason,
                )
                result.status = RunStatus.AWAITING_APPROVAL
                result.pending_approval = approval
                audit_service.save_run(result)
                return result

            if decision.kind == "final":
                result.resolution_message = decision.text
                result.action_taken = state.context.get("action")
                result.analysis = self._build_analysis(state)
                result.status = RunStatus.COMPLETED
                audit_service.save_run(result)
                logger.info("run %s: completed", state.run_id)
                return result

            # kind == "tool_call"
            tool_name = decision.tool_name or ""
            tool_args = dict(decision.tool_args or {})
            tool_result = dispatch_tool(tool_name, tool_args)
            state.record_tool_call(tool_name, tool_args, tool_result)

            audit_service.append_audit_event(
                state.run_id,
                {"event": "tool_call", "tool": tool_name, "args": _redact(tool_args), "result": tool_result},
            )

            status = StepStatus.SUCCESS if tool_result.get("success") else StepStatus.FAILED
            self._record_step(
                result,
                STEP_LABELS.get(tool_name, tool_name),
                tool=tool_name,
                status=status,
                summary=_summarize_tool_result(tool_name, tool_result),
                error=None if tool_result.get("success") else tool_result.get("error"),
            )

            if tool_name == "check_inventory" and tool_result.get("success"):
                data = tool_result["data"]
                verdict = "eligible and in stock" if (data["available"] and data["replacement_eligible"]) else "not currently eligible for an automatic replacement"
                self._record_step(
                    result, "Replacement eligibility evaluated", tool=None, status=StepStatus.SUCCESS,
                    summary=f"Item is {verdict}.",
                )

        # Ran out of iterations without a final answer — fail safe.
        self._record_step(
            result, "Agent stopped", tool=None, status=StepStatus.FAILED,
            summary="Reached the maximum reasoning steps without a resolution.",
        )
        result.status = RunStatus.FAILED
        result.error = "max_iterations_reached"
        audit_service.save_run(result)
        return result

    def _build_analysis(self, state: AgentState) -> AgentAnalysis:
        ctx = state.context
        intent = ctx.get("intent", "general_inquiry")
        priority = ctx.get("priority") or classify_priority(state.customer_request, ctx.get("customer"))
        action = ctx.get("action")
        resolution = {
            "replacement": "Replacement",
            "refund": "Refund",
            "ticket": "Escalated to support",
        }.get((action or {}).get("type"), "Information provided")

        confidence = 0.95
        for tc in state.tool_calls:
            if not tc.result.get("success"):
                confidence -= 0.12
        if resolution == "Escalated to support":
            confidence -= 0.1
        confidence = max(0.4, min(0.97, confidence))

        return AgentAnalysis(intent=intent, priority=priority, resolution=resolution, confidence=round(confidence, 2))

    def _record_step(
        self, result: AgentRunResult, label: str, tool: str | None, status: StepStatus,
        summary: str, error: str | None = None,
    ) -> None:
        step = ExecutionStep(
            step_id=f"STEP-{len(result.steps) + 1}", label=label, tool=tool,
            status=status, summary=summary, error=error,
        )
        result.steps.append(step)
        audit_service.append_audit_event(
            result.run_id,
            {"event": "step", "label": label, "tool": tool, "status": status.value, "summary": summary},
        )


def _redact(args: dict) -> dict:
    # Nothing sensitive currently flows through tool args in this mock
    # system, but keep a redaction seam for real PII/payment fields.
    return args


def _summarize_tool_result(tool_name: str, result: dict) -> str:
    if not result.get("success"):
        detail = result.get("detail")
        base = f"{tool_name} failed: {result.get('error', 'unknown_error')}"
        return f"{base} ({detail})" if detail else base

    data = result.get("data")
    if tool_name == "get_customer" and data:
        return f"{data['name']} ({data['customer_tier']} tier, {data['account_status']})"
    if tool_name == "get_order" and data:
        return f"Order {data['order_id']} — {data['status']}, EUR {data['price']:.2f}"
    if tool_name == "search_knowledge_base" and data:
        titles = ", ".join(d["title"] for d in data)
        return f"Matched policy: {titles}"
    if tool_name == "check_inventory" and data:
        return f"{data['in_stock']} unit(s) in stock (requested {data['requested_quantity']})"
    if tool_name == "create_replacement" and data:
        return f"Replacement {data['replacement_id']} created, ETA {data.get('estimated_delivery')}"
    if tool_name == "create_refund" and data:
        return f"Refund {data['refund_id']} issued for EUR {data['amount']:.2f}"
    if tool_name == "create_support_ticket" and data:
        return f"Ticket {data['ticket_id']} opened ({data['priority']} priority)"
    if tool_name == "send_customer_message" and data:
        return f"Message {data['message_id']} sent via {data['channel']}"
    return "Completed."
