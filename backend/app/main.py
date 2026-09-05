from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.agent.agent import Agent
from app.config import settings
from app.models.agent import (
    AgentRunRequest,
    AgentRunResult,
    ApprovalDecisionRequest,
)
from app.services import audit_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("agentresolve.main")

app = FastAPI(
    title="AgentResolve API",
    description="Autonomous customer-support resolution agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent = Agent()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_configured": bool(settings.anthropic_api_key) if settings.llm_provider == "anthropic" else True,
    }


@app.post("/api/agent/run", response_model=AgentRunResult)
def run_agent(request: AgentRunRequest) -> AgentRunResult:
    try:
        return _agent.run(request)
    except Exception:
        logger.exception("agent run failed")
        raise HTTPException(status_code=500, detail="agent_run_failed")


@app.get("/api/agent/{run_id}", response_model=AgentRunResult)
def get_agent_run(run_id: str) -> AgentRunResult:
    result = audit_service.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    return result


@app.post("/api/approval/{approval_id}/approve", response_model=AgentRunResult)
def approve(approval_id: str, decision: ApprovalDecisionRequest = ApprovalDecisionRequest()) -> AgentRunResult:
    try:
        return _agent.submit_approval_decision(approval_id, decision, approved=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/approval/{approval_id}/reject", response_model=AgentRunResult)
def reject(approval_id: str, decision: ApprovalDecisionRequest = ApprovalDecisionRequest()) -> AgentRunResult:
    try:
        return _agent.submit_approval_decision(approval_id, decision, approved=False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
