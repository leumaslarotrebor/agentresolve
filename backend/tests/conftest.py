from __future__ import annotations

import pytest

from app.services import action_registry, audit_service
from app.services.data_store import reset_store


@pytest.fixture(autouse=True)
def _reset_state():
    """Every test gets a clean mock data store, audit log, and action
    registry so tests never leak inventory/refund/ticket state into
    each other (this is also what makes the idempotency tests meaningful)."""
    reset_store()
    audit_service.reset_all()
    action_registry.reset_all()
    yield
    reset_store()
    audit_service.reset_all()
    action_registry.reset_all()
