from __future__ import annotations

from app.agent.agent import Agent
from app.models.agent import AgentRunRequest, ApprovalDecisionRequest, RunStatus


def make_agent() -> Agent:
    return Agent()


def test_happy_path_replacement():
    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="My laptop arrived damaged, please send a replacement.",
            customer_id="CUST-1001",
            order_id="ORD-5001",
        )
    )
    assert result.status == RunStatus.COMPLETED
    assert result.action_taken["type"] == "replacement"
    assert result.analysis.resolution == "Replacement"
    labels = [s.label for s in result.steps]
    assert "Customer identified" in labels
    assert "Order retrieved" in labels
    assert "Inventory checked" in labels
    assert "Replacement created" in labels


def test_out_of_stock_escalates_to_ticket():
    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="My monitor arrived damaged, send a replacement.",
            customer_id="CUST-1003",
            order_id="ORD-5003",  # PROD-102 has 0 inventory
        )
    )
    assert result.status == RunStatus.COMPLETED
    assert result.action_taken["type"] == "ticket"
    assert "replacement" not in (result.resolution_message or "").lower() or "escalated" in (result.resolution_message or "").lower()


def test_high_value_refund_requires_approval_then_completes():
    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="I want a refund for my damaged laptop.",
            customer_id="CUST-1002",
            order_id="ORD-5002",  # price 1349.00, above threshold
        )
    )
    assert result.status == RunStatus.AWAITING_APPROVAL
    assert result.pending_approval is not None
    assert result.pending_approval.tool_name == "create_refund"

    approved_result = agent.submit_approval_decision(
        result.pending_approval.approval_id,
        ApprovalDecisionRequest(decided_by="test_manager"),
        approved=True,
    )
    assert approved_result.status == RunStatus.COMPLETED
    assert approved_result.action_taken["type"] == "refund"
    assert approved_result.action_taken["amount"] == 1349.0


def test_high_value_refund_rejected_escalates_to_ticket():
    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="I want a refund for my damaged laptop.",
            customer_id="CUST-1002",
            order_id="ORD-5002",
        )
    )
    assert result.status == RunStatus.AWAITING_APPROVAL

    rejected_result = agent.submit_approval_decision(
        result.pending_approval.approval_id,
        ApprovalDecisionRequest(decided_by="test_manager"),
        approved=False,
    )
    assert rejected_result.status == RunStatus.COMPLETED
    assert rejected_result.action_taken["type"] == "ticket"
    # Ensure no refund was actually issued after rejection.
    assert not any(
        e.get("event") == "tool_call" and e.get("tool") == "create_refund" and e["result"].get("success")
        for e in rejected_result.audit_trail
    )


def test_low_value_refund_is_autonomous():
    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="I'd like a refund for this order please.",
            customer_id="CUST-1007",
            order_id="ORD-5008",  # price 89.00, below threshold
        )
    )
    assert result.status == RunStatus.COMPLETED
    assert result.action_taken["type"] == "refund"
    assert result.action_taken["amount"] == 89.0


def test_unknown_customer_handled_gracefully():
    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="My laptop arrived damaged, please replace it.",
            customer_id="CUST-9999",
        )
    )
    assert result.status == RunStatus.COMPLETED
    assert result.action_taken is None
    assert "verify" in (result.resolution_message or "").lower() or "couldn't" in (result.resolution_message or "").lower()


def test_expired_refund_window_rejected_without_approval():
    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="Refund my order from three years ago.",
            customer_id="CUST-1004",
            order_id="ORD-5004",
        )
    )
    assert result.status == RunStatus.COMPLETED
    assert result.action_taken is None
    assert result.pending_approval is None


def test_duplicate_execution_does_not_duplicate_action():
    agent = make_agent()
    req = AgentRunRequest(
        customer_request="My laptop arrived damaged, please send a replacement.",
        customer_id="CUST-1012",
        order_id="ORD-5013",
        idempotency_key="dedupe-key-001",
    )
    first = agent.run(req)
    second = agent.run(req)

    assert first.run_id == second.run_id
    assert first.action_taken["replacement_id"] == second.action_taken["replacement_id"]


def test_unknown_order_handled_gracefully():
    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="Please replace my damaged item.",
            customer_id="CUST-1005",
            order_id="ORD-9999",  # does not exist
        )
    )
    assert result.status == RunStatus.COMPLETED
    assert result.action_taken is None
    assert "order" in (result.resolution_message or "").lower() or "confirm" in (result.resolution_message or "").lower()


def test_agent_run_can_be_retrieved_after_completion():
    from app.services import audit_service

    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="My laptop arrived damaged, please send a replacement.",
            customer_id="CUST-1001",
            order_id="ORD-5001",
        )
    )
    fetched = audit_service.get_run(result.run_id)
    assert fetched is not None
    assert fetched.run_id == result.run_id
    assert fetched.status == RunStatus.COMPLETED
    assert len(fetched.audit_trail) > 0


def test_suspended_account_is_escalated_not_actioned():
    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="My laptop arrived damaged, please send a replacement.",
            customer_id="CUST-1006",  # account_status: suspended
        )
    )
    assert result.status == RunStatus.COMPLETED
    assert result.action_taken["type"] == "ticket"


def test_tool_failure_does_not_hallucinate_success():
    """A replacement request for a non-replacement-eligible product must
    never be reported as a successful replacement."""
    agent = make_agent()
    result = agent.run(
        AgentRunRequest(
            customer_request="My SSD arrived damaged, please replace it.",
            customer_id="CUST-1013",
            order_id="ORD-5024",  # PROD-108, replacement_eligible=False
        )
    )
    assert result.status == RunStatus.COMPLETED
    assert result.action_taken["type"] == "ticket"
    assert "replaced" not in (result.resolution_message or "").lower()
