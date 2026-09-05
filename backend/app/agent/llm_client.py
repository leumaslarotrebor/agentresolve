"""
LLM client abstraction.

`LLMClient.decide_next_step` is the single seam between the agent
orchestration loop (agent.py) and "what should happen next". The real
implementation (AnthropicLLMClient) calls Claude's Messages API with the
tool registry and lets the model choose the next tool call or produce a
final answer — genuine structured tool calling, not an if/else tree.

A deterministic SimulatedPlanner (planner.py) implements the same
interface so the whole project — including the demo scenarios and the
pytest suite — runs without requiring an API key. It is clearly a
fallback: see README limitations.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentState
from app.config import settings
from app.tools.registry import TOOL_DEFINITIONS

logger = logging.getLogger("agentresolve.agent.llm")


@dataclass
class LLMDecision:
    kind: str  # "tool_call" | "final"
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    text: str | None = None
    tool_use_id: str | None = None


class LLMClient(ABC):
    @abstractmethod
    def decide_next_step(self, state: AgentState) -> LLMDecision:
        """Given the conversation so far, decide the next tool call or
        produce the final customer-facing decision."""
        raise NotImplementedError


class LLMClientError(RuntimeError):
    pass


class AnthropicLLMClient(LLMClient):
    """Real structured tool-calling client using the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    def decide_next_step(self, state: AgentState) -> LLMDecision:
        import httpx  # imported lazily so the simulated path never needs it

        if not state.messages:
            state.messages.append({"role": "user", "content": state.customer_request})

        payload = {
            "model": self._model,
            "max_tokens": settings.llm_max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": state.messages,
            "tools": TOOL_DEFINITIONS,
        }
        try:
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Anthropic API call failed: %s", exc)
            raise LLMClientError(f"llm_api_error: {exc}") from exc

        body = resp.json()
        content = body.get("content", [])
        state.messages.append({"role": "assistant", "content": content})

        tool_use_blocks = [b for b in content if b.get("type") == "tool_use"]
        if body.get("stop_reason") == "tool_use" and tool_use_blocks:
            block = tool_use_blocks[0]
            return LLMDecision(
                kind="tool_call",
                tool_name=block["name"],
                tool_args=block.get("input", {}),
                tool_use_id=block.get("id"),
            )

        text_blocks = [b.get("text", "") for b in content if b.get("type") == "text"]
        return LLMDecision(kind="final", text="\n".join(text_blocks).strip())

    def append_tool_result(self, state: AgentState, tool_use_id: str, result: dict[str, Any]) -> None:
        state.messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps(result, default=str),
                    }
                ],
            }
        )


def get_llm_client() -> LLMClient:
    from app.agent.planner import SimulatedPlanner

    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicLLMClient(settings.anthropic_api_key, settings.llm_model)
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        logger.warning(
            "LLM_PROVIDER=anthropic but no ANTHROPIC_API_KEY set; "
            "falling back to the simulated planner."
        )
    return SimulatedPlanner()
