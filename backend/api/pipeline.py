"""DB-backed job pipeline helpers.

Kept free of Selenium so every state change is unit-testable:
  * set_app_status      — guarded lifecycle transitions (no stuck rows)
  * decide_apply        — apply only on LLM "apply" + score >= threshold
  * mark_session_stopped— stop is immediate and persisted
  * finalize_session    — counters always derived from persisted rows
  * create_outreach_draft — drafts stored, never sent
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from core.statuses import (
    ACTIVE_STATUSES, AppStatus, DraftStatus, FailureReason, can_transition, is_terminal,
)

logger = logging.getLogger(__name__)

#: Don't re-apply to the same company within this window (account-safe pacing).
COMPANY_DEDUPE_DAYS = 7


def _now():
    return datetime.now(timezone.utc)


def applies_today(db) -> int:
    """Number of successful applies in the last 24h, from PERSISTED rows —
    survives restarts, unlike the in-memory rate limiter."""
    from datetime import timedelta
    from api.models import Application
    since = _now() - timedelta(hours=24)
    return (db.query(Application)
              .filter(Application.status.in_([AppStatus.APPLIED, AppStatus.APPLIED_PENDING]))
              .filter(Application.timestamp >= since)
              .count())


def daily_cap_reached(db, max_per_day: int) -> bool:
    return applies_today(db) >= max(1, int(max_per_day or 1))


def is_duplicate_company(db, company: str, days: int = COMPANY_DEDUPE_DAYS) -> bool:
    """True if we already applied (or emailed) this company recently."""
    from datetime import timedelta
    from api.models import Application
    company = (company or "").strip()
    if not company:
        return False
    since = _now() - timedelta(days=days)
    row = (db.query(Application)
             .filter(Application.company.ilike(company))
             .filter(Application.status.in_([AppStatus.APPLIED, AppStatus.APPLIED_PENDING,
                                             AppStatus.EMAIL_SENT, AppStatus.EMAIL_DRAFTED]))
             .filter(Application.timestamp >= since)
             .first())
    return row is not None


def set_app_status(
    db, app, status: str, *,
    failure_reason: str = "",
    error_message: Optional[str] = None,
    emit: bool = True,
    commit: bool = True,
) -> bool:
    """Transition an Application row. Invalid transitions (e.g. out of a
    terminal state) are refused, so 'applied' can never be clobbered and no
    row silently regresses. Returns True if the row changed."""
    current = app.status or AppStatus.QUEUED
    if current != status and not can_transition(current, status):
        logger.warning("Refused status transition %s → %s for application %s",
                       current, status, app.id)
        return False

    app.status = status
    if failure_reason:
        app.failure_reason = failure_reason
    if error_message is not None:
        app.error_message = error_message
    app.updated_at = _now()

    # Audit trail (same transaction as the status change)
    try:
        from core.audit import log_event
        log_event(db, app.session_id, "status_change",
                  {"status": status, "failure_reason": failure_reason or "",
                   "job_title": app.job_title or "", "company": app.company or ""},
                  application_id=app.id, commit=False)
    except Exception:
        pass

    if commit:
        db.commit()
        if status == AppStatus.SKIPPED:
            try:
                from api.models import Session as SessionModel
                from core.ignored_jobs import maybe_auto_ignore
                sess = db.get(SessionModel, app.session_id) if app.session_id else None
                maybe_auto_ignore(db, app, enabled=bool(getattr(sess, "auto_ignore_skipped", True)))
            except Exception:
                logger.exception("Failed to auto-ignore skipped application %s", app.id)

    if emit:
        try:
            import core.tracker as tracker
            tracker.job_status(app.id, status,
                               failure_reason=failure_reason or (app.failure_reason or ""),
                               classification=app.classification or "",
                               title=app.job_title or "", company=app.company or "")
        except Exception:
            pass
    return True


def decide_apply(recommendation: str, score: int, threshold: int) -> tuple[bool, str]:
    """Apply ONLY when the LLM recommends apply AND the score meets the
    threshold. A skip recommendation is honoured unconditionally (no override
    setting exists yet — by design)."""
    if (recommendation or "").strip().lower() != "apply":
        return False, FailureReason.LLM_RECOMMENDED_SKIP
    if score < threshold:
        return False, FailureReason.BELOW_THRESHOLD
    return True, ""


def mark_session_stopped(db, session_id: int) -> int:
    """Immediately persist the stop: session row → stopped, and every
    non-terminal application row → stopped. Returns # of rows stopped."""
    from api.models import Application, Session as SessionModel

    stopped_rows = 0
    sess = db.get(SessionModel, session_id)
    if sess and sess.status == "running":
        sess.status = "stopped"
        sess.ended_at = _now()

    apps = (db.query(Application)
              .filter(Application.session_id == session_id)
              .filter(Application.status.notin_(
                  [AppStatus.APPLIED, AppStatus.SKIPPED, AppStatus.FAILED,
                   AppStatus.STOPPED, AppStatus.EMAIL_SENT]))
              .all())
    for app in apps:
        # email_drafted / manual_review rows stay reviewable — only halt rows
        # the automation was actively working on.
        if app.status in ACTIVE_STATUSES:
            if set_app_status(db, app, AppStatus.STOPPED,
                              failure_reason=FailureReason.SESSION_STOPPED,
                              emit=False, commit=False):
                stopped_rows += 1
    from core.audit import log_event
    log_event(db, session_id, "session_stopped", {"stopped_rows": stopped_rows}, commit=False)
    db.commit()
    refresh_session_counters(db, session_id)
    return stopped_rows


def refresh_session_counters(db, session_id: int) -> None:
    """Session counters always reflect persisted application rows."""
    from api.models import Application, Session as SessionModel
    sess = db.get(SessionModel, session_id)
    if not sess:
        return
    rows = db.query(Application).filter_by(session_id=session_id).all()
    sess.applied = sum(1 for a in rows if a.status in (AppStatus.APPLIED, AppStatus.APPLIED_PENDING))
    sess.skipped = sum(1 for a in rows if a.status == AppStatus.SKIPPED)
    sess.errors  = sum(1 for a in rows if a.status == AppStatus.FAILED)
    db.commit()


def session_status_counts(db, session_id: int) -> dict[str, int]:
    from api.models import Application
    counts: dict[str, int] = {s: 0 for s in AppStatus.ALL}
    rows = db.query(Application).filter_by(session_id=session_id).all()
    for a in rows:
        counts[a.status] = counts.get(a.status, 0) + 1
    counts["total"] = len(rows)
    return counts


def finalize_session(db, session_id: int, *, stopped: bool, failed: bool = False) -> None:
    """End-of-run cleanup: no row may remain in an in-flight state."""
    from api.models import Application, Session as SessionModel

    apps = (db.query(Application)
              .filter(Application.session_id == session_id)
              .filter(Application.status.in_(list(ACTIVE_STATUSES)))
              .all())
    for app in apps:
        target = AppStatus.STOPPED if stopped else AppStatus.FAILED
        reason = (FailureReason.SESSION_STOPPED if stopped
                  else FailureReason.UNSUPPORTED_FLOW)
        set_app_status(db, app, target, failure_reason=reason, emit=False, commit=False)
    db.commit()

    refresh_session_counters(db, session_id)
    sess = db.get(SessionModel, session_id)
    if sess and sess.status == "running":
        sess.status = "failed" if failed else ("stopped" if stopped else "completed")
        sess.ended_at = _now()
        db.commit()

    from core.audit import log_event
    log_event(db, session_id, "session_finalized",
              {"stopped": stopped, "failed": failed,
               "applied": sess.applied if sess else 0,
               "skipped": sess.skipped if sess else 0,
               "errors": sess.errors if sess else 0})


def create_outreach_draft(
    db, app, cv_data, finding, llm=None, commit: bool = True,
):
    """Generate and STORE an outreach draft (status=draft). Never sends."""
    from api.models import OutreachDraft
    from core.outreach import generate_outreach_draft

    content = generate_outreach_draft(
        cv_data, app.job_title or "the role", app.company or "",
        app.job_url or "", llm=llm,
    )
    draft = OutreachDraft(
        application_id=app.id,
        session_id=app.session_id,
        recruiter_email=finding.email,
        email_source=finding.source,
        email_source_url=finding.source_url or app.job_url or "",
        subject=content.subject,
        body=content.body,
        status=DraftStatus.DRAFT,
    )
    db.add(draft)
    if commit:
        db.commit()
        db.refresh(draft)
    return draft
