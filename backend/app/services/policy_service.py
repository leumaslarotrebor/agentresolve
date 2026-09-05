"""
Lightweight retrieval over the support-policy knowledge base.

This deliberately isn't a vector-DB/RAG pipeline - the point of this project
is agent orchestration and tool calling, not embeddings - but it's a real
retrieval step the agent depends on for its decisions, not a hardcoded
lookup table.
"""
from __future__ import annotations

from app.services.data_store import get_store


def search_knowledge_base(query: str, top_k: int = 3) -> list[dict[str, str]]:
    """Keyword-overlap search over policy documents. Returns ranked matches."""
    store = get_store()
    query_terms = {t.lower() for t in query.split() if len(t) > 2}

    scored: list[tuple[int, dict]] = []
    for doc in store.knowledge:
        haystack = f"{doc['topic']} {doc['title']} {doc['content']}".lower()
        score = sum(1 for term in query_terms if term in haystack)
        # Always give topic-name matches a boost so e.g. "refund" reliably
        # surfaces POLICY-REFUND even with a short query.
        if doc["topic"].lower() in query.lower():
            score += 5
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    results = [doc for _, doc in scored[:top_k]]

    if not results:
        # Fall back to returning the escalation policy so the agent always
        # has *something* actionable rather than an empty retrieval.
        results = [d for d in store.knowledge if d["topic"] == "escalation"][:1]

    return [
        {"id": d["id"], "topic": d["topic"], "title": d["title"], "content": d["content"]}
        for d in results
    ]


def get_policy_by_topic(topic: str) -> dict[str, str] | None:
    store = get_store()
    for doc in store.knowledge:
        if doc["topic"] == topic:
            return doc
    return None
