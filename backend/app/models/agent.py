from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING_APPROVAL = "pending_approval"
    SKIPPED = "skipped"


class ExecutionStep(BaseModel):
    """One entry in the user-facing agent execution timeline."""

    step_id: str
    label: str
    tool: str | None = None
    status: StepStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str
    error: str | None = None


class RunStatus(str, Enum):
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(BaseModel):
    approval_id: str
    run_id: str
    action: str
    tool_name: str
    tool_args: dict[str, Any]
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None


class AgentRunRequest(BaseModel):
    customer_request: str = Field(..., min_length=3, max_length=2000)
    customer_id: str | None = None
    order_id: str | None = None
    idempotency_key: str | None = None


class AgentAnalysis(BaseModel):
    intent: str
    priority: str
    resolution: str
    confidence: float


class AgentRunResult(BaseModel):
    run_id: str
    status: RunStatus
    analysis: AgentAnalysis | None = None
    steps: list[ExecutionStep] = Field(default_factory=list)
    resolution_message: str | None = None
    action_taken: dict[str, Any] | None = None
    pending_approval: ApprovalRequest | None = None
    audit_trail: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ApprovalDecisionRequest(BaseModel):
    decided_by: str = "human_reviewer"
    note: str | None = None
