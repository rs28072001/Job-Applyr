"""Review queue + outreach draft endpoints.

GET  /api/review/queue                     — manual-review jobs + email drafts
POST /api/review/applications/{id}/resolve — mark_applied | dismiss
GET  /api/outreach                         — list drafts
PUT  /api/outreach/{id}                    — edit subject/body (draft only)
POST /api/outreach/{id}/approve            — explicit human approval
POST /api/outreach/{id}/discard
POST /api/outreach/{id}/send               — ONLY in send_after_approval mode,
                                             only for approved drafts
POST /api/outreach/{id}/mark_sent          — user sent it from their own client

Emails are never sent automatically; draft_only is the default mode.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from api.auth import get_current_user
from api.database import get_db
from api.models import (
    Application, Config as ConfigModel, OutreachDraft, OutreachSendLog, User,
)
from api.schemas import (
    ApplicationRead, OutreachDraftRead, OutreachDraftUpdate,
    ReviewQueueResponse, ReviewResolveRequest, SmtpTestRequest,
)
from core.outreach import (
    OutreachSendError, send_outreach_email, send_test_email, validate_smtp_settings,
)
from core.statuses import AppStatus, DraftStatus, OutreachMode


def _smtp_settings(cfg) -> dict:
    return {
        "host": getattr(cfg, "smtp_host", ""),
        "port": getattr(cfg, "smtp_port", 587),
        "username": getattr(cfg, "smtp_username", ""),
        "password": getattr(cfg, "smtp_password", ""),
        "from_address": getattr(cfg, "smtp_from", ""),
    }

router = APIRouter()


def _draft_read(draft: OutreachDraft, db: DBSession) -> OutreachDraftRead:
    app = db.get(Application, draft.application_id) if draft.application_id else None
    data = OutreachDraftRead.model_validate(draft)
    if app:
        data.job_title = app.job_title or ""
        data.company = app.company or ""
        data.job_url = app.job_url or ""
    return data


@router.get("/api/review/queue", response_model=ReviewQueueResponse)
def review_queue(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    apps = (db.query(Application)
              .filter(Application.status == AppStatus.MANUAL_REVIEW)
              .order_by(Application.timestamp.desc())
              .limit(200).all())
    drafts = (db.query(OutreachDraft)
                .filter(OutreachDraft.status.in_([DraftStatus.DRAFT, DraftStatus.APPROVED]))
                .order_by(OutreachDraft.created_at.desc())
                .limit(200).all())
    skipped = (db.query(Application)
                 .filter(Application.status == AppStatus.SKIPPED)
                 .order_by(Application.timestamp.desc())
                 .limit(100).all())
    saved = (db.query(Application)
               .filter(Application.status == AppStatus.SAVED)
               .order_by(Application.timestamp.desc())
               .limit(200).all())
    return ReviewQueueResponse(
        manual_review=[ApplicationRead.model_validate(a) for a in apps],
        drafts=[_draft_read(d, db) for d in drafts],
        skipped=[ApplicationRead.model_validate(a) for a in skipped],
        saved=[ApplicationRead.model_validate(a) for a in saved],
    )


@router.post("/api/review/applications/{app_id}/resolve")
def resolve_review_item(app_id: int, body: ReviewResolveRequest,
                        db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    if app.status not in (AppStatus.MANUAL_REVIEW, AppStatus.SAVED):
        raise HTTPException(409, f"Application is '{app.status}', not resolvable")

    if body.action == "mark_applied":
        app.status = AppStatus.APPLIED
        app.error_message = "Marked as applied manually by user"
    else:
        app.status = AppStatus.SKIPPED
        app.error_message = "Removed by user"
    app.updated_at = datetime.now(timezone.utc)
    db.commit()

    if app.session_id:
        from api.pipeline import refresh_session_counters
        refresh_session_counters(db, app.session_id)
    return {"status": app.status}


# ── Outreach drafts ──────────────────────────────────────────────────────────

@router.get("/api/outreach", response_model=list[OutreachDraftRead])
def list_drafts(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    drafts = db.query(OutreachDraft).order_by(OutreachDraft.created_at.desc()).limit(200).all()
    return [_draft_read(d, db) for d in drafts]


def _get_draft(draft_id: int, db: DBSession) -> OutreachDraft:
    draft = db.get(OutreachDraft, draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    return draft


@router.put("/api/outreach/{draft_id}", response_model=OutreachDraftRead)
def edit_draft(draft_id: int, body: OutreachDraftUpdate,
               db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    draft = _get_draft(draft_id, db)
    if draft.status not in (DraftStatus.DRAFT, DraftStatus.APPROVED):
        raise HTTPException(409, "Only unsent drafts can be edited")
    if body.subject is not None:
        draft.subject = body.subject
    if body.body is not None:
        draft.body = body.body
    # Edits to an approved draft require re-approval.
    draft.status = DraftStatus.DRAFT
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _draft_read(draft, db)


@router.post("/api/outreach/{draft_id}/approve", response_model=OutreachDraftRead)
def approve_draft(draft_id: int, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    draft = _get_draft(draft_id, db)
    if draft.status != DraftStatus.DRAFT:
        raise HTTPException(409, f"Draft is '{draft.status}', expected 'draft'")
    draft.status = DraftStatus.APPROVED
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _draft_read(draft, db)


@router.post("/api/outreach/{draft_id}/discard", response_model=OutreachDraftRead)
def discard_draft(draft_id: int, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    draft = _get_draft(draft_id, db)
    if draft.status == DraftStatus.SENT:
        raise HTTPException(409, "Sent drafts cannot be discarded")
    draft.status = DraftStatus.DISCARDED
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    _sync_application_after_discard(draft, db)
    return _draft_read(draft, db)


def _sync_application_after_discard(draft: OutreachDraft, db: DBSession) -> None:
    if not draft.application_id:
        return
    app = db.get(Application, draft.application_id)
    if app and app.status == AppStatus.EMAIL_DRAFTED:
        app.status = AppStatus.SKIPPED
        app.updated_at = datetime.now(timezone.utc)
        db.commit()


def _mark_sent(draft: OutreachDraft, db: DBSession, method: str) -> None:
    now = datetime.now(timezone.utc)
    draft.status = DraftStatus.SENT
    draft.sent_at = now
    draft.updated_at = now
    app = db.get(Application, draft.application_id) if draft.application_id else None
    if app and app.status in (AppStatus.EMAIL_DRAFTED, AppStatus.MANUAL_REVIEW):
        app.status = AppStatus.EMAIL_SENT
        app.updated_at = now
    # Immutable send log: job, recipient, subject, timestamp, method.
    db.add(OutreachSendLog(
        draft_id=draft.id,
        application_id=draft.application_id,
        session_id=draft.session_id,
        job_title=app.job_title if app else "",
        company=app.company if app else "",
        recipient=draft.recruiter_email,
        subject=draft.subject,
        method=method,
        sent_at=now,
    ))
    db.commit()
    from core.audit import log_event
    log_event(db, draft.session_id, "outreach_sent",
              {"draft_id": draft.id, "recipient": draft.recruiter_email,
               "subject": draft.subject, "method": method},
              application_id=draft.application_id)


@router.post("/api/outreach/{draft_id}/send", response_model=OutreachDraftRead)
def send_draft(draft_id: int, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Send an APPROVED draft via the user's own SMTP — allowed only when the
    global outreach mode is 'send_after_approval'."""
    draft = _get_draft(draft_id, db)
    cfg = db.get(ConfigModel, 1)
    mode = (getattr(cfg, "outreach_mode", None) or OutreachMode.DRAFT_ONLY)
    try:
        send_outreach_email(draft, mode, _smtp_settings(cfg))
    except OutreachSendError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"SMTP send failed: {e}")
    _mark_sent(draft, db, method="smtp")
    return _draft_read(draft, db)


@router.post("/api/outreach/{draft_id}/mark_sent", response_model=OutreachDraftRead)
def mark_draft_sent(draft_id: int, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    """User copied the draft into their own mail client and sent it there."""
    draft = _get_draft(draft_id, db)
    if draft.status not in (DraftStatus.DRAFT, DraftStatus.APPROVED):
        raise HTTPException(409, f"Draft is '{draft.status}'")
    _mark_sent(draft, db, method="user_mail_client")
    return _draft_read(draft, db)


# ── SMTP configuration check & test email ────────────────────────────────────

@router.get("/api/outreach/smtp/validate")
def smtp_validate(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    cfg = db.get(ConfigModel, 1)
    problems = validate_smtp_settings(_smtp_settings(cfg))
    return {"ok": not problems, "problems": problems}


@router.post("/api/outreach/smtp/test")
def smtp_send_test(body: SmtpTestRequest, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Send a single test email to the user's own address using saved SMTP
    settings (optionally overridden by the request body, e.g. before saving)."""
    cfg = db.get(ConfigModel, 1)
    settings = _smtp_settings(cfg)
    overrides = body.model_dump(exclude_unset=True, exclude_none=True)
    for k in ("host", "port", "username", "password", "from_address"):
        if k in overrides and overrides[k] != "***":
            settings[k] = overrides[k]
    try:
        recipient = send_test_email(settings, body.to or "")
    except OutreachSendError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "sent_to": recipient}


@router.get("/api/outreach/send_log")
def outreach_send_log(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (db.query(OutreachSendLog)
              .order_by(OutreachSendLog.sent_at.desc())
              .limit(200).all())
    return [{
        "id": r.id, "draft_id": r.draft_id, "application_id": r.application_id,
        "job_title": r.job_title, "company": r.company, "recipient": r.recipient,
        "subject": r.subject, "method": r.method, "sent_at": r.sent_at,
    } for r in rows]
