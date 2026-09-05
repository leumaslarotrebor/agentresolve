from __future__ import annotations

from app.tools.action_tools import create_refund, create_replacement, create_support_ticket
from app.tools.customer_tools import get_customer
from app.tools.inventory_tools import check_inventory
from app.tools.knowledge_tools import search_knowledge_base
from app.tools.order_tools import get_order


def test_get_customer_by_id():
    result = get_customer({"customer_id": "CUST-1001"})
    assert result["success"] is True
    assert result["data"]["name"] == "Aoife Byrne"


def test_get_customer_not_found():
    result = get_customer({"customer_id": "CUST-0000"})
    assert result["success"] is False
    assert result["error"] == "customer_not_found"


def test_get_customer_missing_args():
    result = get_customer({})
    assert result["success"] is False
    assert "missing_identifier" in result["error"]


def test_get_order_by_id():
    result = get_order({"order_id": "ORD-5001"})
    assert result["success"] is True
    assert result["data"]["customer_id"] == "CUST-1001"


def test_check_inventory_out_of_stock():
    result = check_inventory({"product_id": "PROD-102"})
    assert result["success"] is True
    assert result["data"]["available"] is False


def test_search_knowledge_base_returns_refund_policy():
    result = search_knowledge_base({"query": "refund policy"})
    assert result["success"] is True
    assert any(d["topic"] == "refund" for d in result["data"])


def test_create_replacement_insufficient_inventory():
    result = create_replacement({"order_id": "ORD-5003", "reason": "damaged"})
    assert result["success"] is False
    assert result["error"] == "insufficient_inventory"


def test_create_replacement_idempotent():
    first = create_replacement({"order_id": "ORD-5001", "reason": "damaged", "idempotency_key": "k1"})
    second = create_replacement({"order_id": "ORD-5001", "reason": "damaged", "idempotency_key": "k1"})
    assert first["success"] is True
    assert second.get("idempotent_replay") is True
    assert first["data"]["replacement_id"] == second["data"]["replacement_id"]


def test_create_refund_requires_approval_above_threshold():
    result = create_refund({"order_id": "ORD-5002", "amount": 500, "reason": "damaged"})
    assert result["success"] is False
    assert result["error"] == "approval_required"


def test_create_refund_autonomous_below_threshold():
    result = create_refund({"order_id": "ORD-5008", "amount": 50, "reason": "damaged"})
    assert result["success"] is True
    assert result["data"]["status"] == "issued"


def test_create_support_ticket_unknown_customer():
    result = create_support_ticket(
        {"customer_id": "CUST-0000", "subject": "test", "description": "test"}
    )
    assert result["success"] is False
    assert result["error"] == "customer_not_found"


def test_get_order_unknown_id():
    result = get_order({"order_id": "ORD-0000"})
    assert result["success"] is False
    assert result["error"] == "order_not_found"


def test_create_refund_invalid_parameters_missing_required_field():
    # 'amount' is required and missing entirely.
    result = create_refund({"order_id": "ORD-5001", "reason": "damaged"})
    assert result["success"] is False
    assert "invalid_arguments" in result["error"]


def test_create_refund_invalid_parameter_type():
    result = create_refund({"order_id": "ORD-5001", "amount": "not-a-number", "reason": "damaged"})
    assert result["success"] is False
    assert "invalid_arguments" in result["error"]


def test_check_inventory_unknown_product():
    result = check_inventory({"product_id": "PROD-000"})
    assert result["success"] is False
    assert result["error"] == "product_not_found"


def test_create_replacement_order_not_found():
    result = create_replacement({"order_id": "ORD-0000", "reason": "damaged"})
    assert result["success"] is False
    assert result["error"] == "order_not_found"


def test_registry_unknown_tool_name_fails_safely():
    from app.tools.registry import dispatch_tool

    result = dispatch_tool("delete_all_customers", {})
    assert result["success"] is False
    assert "unknown_tool" in result["error"]


def test_registry_tool_exception_is_caught_not_raised():
    from unittest.mock import patch

    from app.tools import registry

    def _boom(_args):
        raise RuntimeError("simulated backend outage")

    with patch.dict(registry.TOOL_IMPLEMENTATIONS, {"get_customer": _boom}):
        result = registry.dispatch_tool("get_customer", {"customer_id": "CUST-1001"})
    assert result["success"] is False
    assert "tool_execution_failed" in result["error"]
