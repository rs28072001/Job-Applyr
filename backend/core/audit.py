"""Append-only session audit log helpers."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def log_event(db, session_id, event_type: str, detail: dict | None = None,
              application_id=None, commit: bool = True) -> None:
    """Write one audit row. Never raises — auditing must not break the run."""
    try:
        from api.models import AuditEvent
        db.add(AuditEvent(
            session_id=session_id,
            application_id=application_id,
            event_type=event_type,
            detail=detail or {},
        ))
        if commit:
            db.commit()
    except Exception:
        logger.exception("Failed to write audit event %s", event_type)
        try:
            db.rollback()
        except Exception:
            pass
