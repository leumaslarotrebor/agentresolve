from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] in {"simulated", "anthropic"}


def test_run_agent_endpoint_happy_path():
    resp = client.post(
        "/api/agent/run",
        json={
            "customer_request": "My laptop arrived damaged, please send a replacement.",
            "customer_id": "CUST-1001",
            "order_id": "ORD-5001",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["action_taken"]["type"] == "replacement"


def test_run_agent_endpoint_rejects_short_request():
    resp = client.post("/api/agent/run", json={"customer_request": "hi"})
    assert resp.status_code == 422  # pydantic min_length validation


def test_get_agent_run_not_found():
    resp = client.get("/api/agent/RUN-doesnotexist")
    assert resp.status_code == 404


def test_get_agent_run_after_run():
    run_resp = client.post(
        "/api/agent/run",
        json={
            "customer_request": "My laptop arrived damaged, please send a replacement.",
            "customer_id": "CUST-1005",
        },
    )
    run_id = run_resp.json()["run_id"]
    fetch_resp = client.get(f"/api/agent/{run_id}")
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["run_id"] == run_id


def test_approval_endpoint_full_cycle():
    run_resp = client.post(
        "/api/agent/run",
        json={
            "customer_request": "I want a refund for my damaged laptop.",
            "customer_id": "CUST-1002",
            "order_id": "ORD-5002",
        },
    )
    body = run_resp.json()
    assert body["status"] == "awaiting_approval"
    approval_id = body["pending_approval"]["approval_id"]

    approve_resp = client.post(
        f"/api/approval/{approval_id}/approve",
        json={"decided_by": "api_test_manager"},
    )
    assert approve_resp.status_code == 200
    approved_body = approve_resp.json()
    assert approved_body["status"] == "completed"
    assert approved_body["action_taken"]["type"] == "refund"


def test_approval_endpoint_unknown_approval_id():
    resp = client.post("/api/approval/APR-doesnotexist/approve", json={})
    assert resp.status_code == 404


def test_reject_endpoint_escalates_to_ticket():
    run_resp = client.post(
        "/api/agent/run",
        json={
            "customer_request": "I want a refund for my damaged laptop.",
            "customer_id": "CUST-1009",
            "order_id": "ORD-5010",
        },
    )
    approval_id = run_resp.json()["pending_approval"]["approval_id"]
    reject_resp = client.post(f"/api/approval/{approval_id}/reject", json={"decided_by": "api_test_manager"})
    assert reject_resp.status_code == 200
    body = reject_resp.json()
    assert body["status"] == "completed"
    assert body["action_taken"]["type"] == "ticket"
