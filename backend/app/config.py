"""
Centralized configuration for AgentResolve.

All tunables (LLM provider/model, business-rule thresholds, data paths) live
here and are overridable via environment variables / .env, so the agent's
behaviour is never hardcoded across the codebase.
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    # --- LLM provider configuration -------------------------------------
    # "anthropic" uses the real Claude API with structured tool calling.
    # "simulated" uses a deterministic local planner (see agent/planner.py)
    # so the project is fully runnable/testable without an API key.
    llm_provider: str = os.getenv("LLM_PROVIDER", "simulated")
    llm_model: str = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    llm_max_tool_iterations: int = int(os.getenv("LLM_MAX_TOOL_ITERATIONS", "8"))

    # --- Business rules ---------------------------------------------------
    refund_auto_approval_threshold_eur: float = float(
        os.getenv("REFUND_AUTO_APPROVAL_THRESHOLD_EUR", "100.0")
    )
    replacement_window_days: int = int(os.getenv("REPLACEMENT_WINDOW_DAYS", "30"))
    refund_window_days: int = int(os.getenv("REFUND_WINDOW_DAYS", "30"))

    # --- App / data ---------------------------------------------------------
    data_dir: Path = Path(os.getenv("DATA_DIR", str(Path(__file__).parent / "data")))
    audit_log_path: Path = Path(
        os.getenv("AUDIT_LOG_PATH", str(Path(__file__).parent / "data" / "audit_log.jsonl"))
    )
    cors_allow_origins: list[str] = os.getenv(
        "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")

    model_config = ConfigDict(arbitrary_types_allowed=True)


settings = Settings()
