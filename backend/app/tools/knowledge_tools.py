from __future__ import annotations

import logging

from pydantic import BaseModel, ValidationError

from app.services.policy_service import search_knowledge_base as _search

logger = logging.getLogger("agentresolve.tools.knowledge")


class SearchKnowledgeBaseArgs(BaseModel):
    query: str
    top_k: int = 3


def search_knowledge_base(args: dict) -> dict:
    """Search the support policy knowledge base for relevant documents."""
    try:
        parsed = SearchKnowledgeBaseArgs(**args)
    except ValidationError as e:
        return {"success": False, "error": f"invalid_arguments: {e}"}

    results = _search(parsed.query, top_k=parsed.top_k)
    logger.info("search_knowledge_base: query=%r -> %d results", parsed.query, len(results))
    if not results:
        return {"success": False, "error": "no_policy_found"}
    return {"success": True, "data": results}
