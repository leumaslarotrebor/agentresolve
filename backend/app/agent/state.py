from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRecord:
    tool: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass
class AgentState:
    """Mutable state threaded through a single agent run."""

    run_id: str
    customer_request: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)  # scratch space:
    # customer, order, policy docs, inventory result, etc. accumulated as
    # tools are called, so later steps (and the planner) can reason over
    # what's already known instead of re-fetching it.
    awaiting_approval: dict[str, Any] | None = None
    finished: bool = False
    final_message: str | None = None

    def record_tool_call(self, tool: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        self.tool_calls.append(ToolCallRecord(tool=tool, args=args, result=result))
        if result.get("success"):
            data = result.get("data")
            if tool == "get_customer" and data:
                self.context["customer"] = data
            elif tool == "get_order" and data:
                self.context["order"] = data
            elif tool == "search_knowledge_base" and data:
                self.context.setdefault("policies", [])
                self.context["policies"].extend(data)
            elif tool == "check_inventory" and data:
                self.context["inventory"] = data
            elif tool == "create_replacement" and data:
                self.context["action"] = {"type": "replacement", **data}
            elif tool == "create_refund" and data:
                self.context["action"] = {"type": "refund", **data}
            elif tool == "create_support_ticket" and data:
                self.context["action"] = {"type": "ticket", **data}
