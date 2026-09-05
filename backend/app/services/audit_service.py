"""
Audit trail + run/approval registry.

Every tool call and agent decision is recorded here so a run can be
inspected after the fact (GET /api/agent/{run_id}) and so the human-approval
workflow has somewhere durable-enough to hang pending approvals.

Persistence is intentionally simple (in-memory dict + append-only JSONL log)
since this is a local demo project; see README production roadmap for how
this would become a real audit store.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.models.agent import AgentRunResult, ApprovalRequest

_lock = threading.Lock()
_runs: dict[str, AgentRunResult] = {}
_approvals: dict[str, ApprovalRequest] = {}
# idempotency_key -> run_id, so re-submitting the same logical request
# doesn't execute duplicate business actions.
_idempotency_index: dict[str, str] = {}


def save_run(result: AgentRunResult) -> None:
    with _lock:
        _runs[result.run_id] = result


def get_run(run_id: str) -> AgentRunResult | None:
    with _lock:
        return _runs.get(run_id)


def register_idempotency_key(key: str, run_id: str) -> str | None:
    """Returns an existing run_id if this key was already used, else None."""
    with _lock:
        existing = _idempotency_index.get(key)
        if existing:
            return existing
        _idempotency_index[key] = run_id
        return None


def save_approval(approval: ApprovalRequest) -> None:
    with _lock:
        _approvals[approval.approval_id] = approval


def get_approval(approval_id: str) -> ApprovalRequest | None:
    with _lock:
        return _approvals.get(approval_id)


def append_audit_event(run_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Appends a structured audit event both to the run's in-memory trail
    and to the append-only JSONL audit log on disk."""
    record = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    with _lock:
        run = _runs.get(run_id)
        if run is not None:
            run.audit_trail.append(record)
        _write_log_line(record)
    return record


def _write_log_line(record: dict[str, Any]) -> None:
    try:
        path: Path = settings.audit_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError:
        # Audit logging must never crash the agent run; a disk failure here
        # is reported but not fatal to the customer-facing flow.
        pass


def reset_all() -> None:
    """Used by tests to clear state between cases."""
    with _lock:
        _runs.clear()
        _approvals.clear()
        _idempotency_index.clear()
