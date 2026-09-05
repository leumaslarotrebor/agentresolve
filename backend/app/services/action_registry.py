"""
Tracks business actions (replacements, refunds, tickets) that tools have
created, keyed by idempotency key, so re-running the same request never
creates duplicate real-world actions.
"""
from __future__ import annotations

import itertools
import threading
from typing import Any

_lock = threading.Lock()
_actions_by_key: dict[str, dict[str, Any]] = {}
_replacement_seq = itertools.count(90001)
_refund_seq = itertools.count(70001)
_ticket_seq = itertools.count(50001)
_message_seq = itertools.count(30001)


def get_existing(idempotency_key: str | None) -> dict[str, Any] | None:
    if not idempotency_key:
        return None
    with _lock:
        return _actions_by_key.get(idempotency_key)


def register(idempotency_key: str | None, record: dict[str, Any]) -> None:
    if not idempotency_key:
        return
    with _lock:
        _actions_by_key[idempotency_key] = record


def next_replacement_id() -> str:
    return f"R{next(_replacement_seq)}"


def next_refund_id() -> str:
    return f"RF{next(_refund_seq)}"


def next_ticket_id() -> str:
    return f"TCK{next(_ticket_seq)}"


def next_message_id() -> str:
    return f"MSG{next(_message_seq)}"


def reset_all() -> None:
    global _replacement_seq, _refund_seq, _ticket_seq, _message_seq
    with _lock:
        _actions_by_key.clear()
        _replacement_seq = itertools.count(90001)
        _refund_seq = itertools.count(70001)
        _ticket_seq = itertools.count(50001)
        _message_seq = itertools.count(30001)
