"""POST /api/session/start  ·  POST /api/session/stop  ·  GET /api/session/status"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from api.auth import get_current_user
from api.database import get_db
from api.models import Session as SessionModel, CVProfile, Config as ConfigModel, User
from api.schemas import SessionStartRequest, SessionStatus
from core.llm_provider import get_llm_settings, is_llm_configured, validate_llm_settings, LLMConfigError
import api.session_manager as sm

router = APIRouter()


@router.post("/api/session/start")
def start_session(body: SessionStartRequest, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    if sm.is_running():
        raise HTTPException(409, "A session is already running. Stop it first.")

    # Validate config is set up
    cfg = db.get(ConfigModel, 1)
    if not cfg or not is_llm_configured(cfg):
        raise HTTPException(400, "LLM credentials not configured. Complete setup first.")
    try:
        validate_llm_settings(get_llm_settings(cfg))
    except LLMConfigError as e:
        raise HTTPException(400, str(e))

    # Resolve keywords: from request or from active CV profile
    keywords = body.keywords
    if not keywords:
        cv = db.query(CVProfile).filter_by(is_active=True).order_by(CVProfile.id.desc()).first()
        keywords = cv.job_titles if cv else ["Software Engineer"]

    # Create session row
    sess = SessionModel(
        platform=body.platform, mode=body.mode, location=body.location,
        job_target=body.job_target, confidence_threshold=body.confidence_threshold,
        keywords=keywords, status="running",
        easy_apply_only=body.easy_apply_only,
        include_external_review=body.include_external_review,
        outreach_mode=body.outreach_mode,
        hide_previously_skipped=body.hide_previously_skipped,
        auto_ignore_skipped=body.auto_ignore_skipped,
        date_posted_filter=body.date_posted_filter,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)

    run_kwargs = {
        "platform": body.platform, "mode": body.mode, "location": body.location,
        "job_target": body.job_target, "confidence_threshold": body.confidence_threshold,
        "keywords": keywords,
        "easy_apply_only": body.easy_apply_only,
        "include_external_review": body.include_external_review,
        "outreach_mode": body.outreach_mode,
        "hide_previously_skipped": body.hide_previously_skipped,
        "auto_ignore_skipped": body.auto_ignore_skipped,
        "date_posted_filter": body.date_posted_filter,
    }
    sm.start(sess.id, run_kwargs)
    return {"status": "started", "session_id": sess.id}


@router.post("/api/session/stop")
def stop_session(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Idempotent: signals the worker, closes Chrome, and immediately persists
    'stopped' on the session row and all in-flight application rows."""
    if not sm.is_running():
        # Defensive cleanup — make sure no session/application row is left
        # marked running even if the worker died unexpectedly.
        from api.pipeline import mark_session_stopped
        stale = db.query(SessionModel).filter_by(status="running").all()
        for s in stale:
            mark_session_stopped(db, s.id)
        return {"status": "stopped", "note": "no active session"}
    sm.stop()
    return {"status": "stopped"}


@router.get("/api/session/status", response_model=SessionStatus)
def session_status(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Live status + counters derived from PERSISTED application rows."""
    from api.pipeline import session_status_counts

    session_id = sm.current_session_id()
    sess = None
    if session_id is None:
        # Fall back to the most recent session so the dashboard can show
        # final persisted counts after completion/stop.
        sess = db.query(SessionModel).order_by(SessionModel.id.desc()).first()
        session_id = sess.id if sess else None
    else:
        sess = db.get(SessionModel, session_id)

    counts = session_status_counts(db, session_id) if session_id else {}
    return SessionStatus(
        is_running=sm.is_running(),
        session_id=sm.current_session_id(),
        started_at=sm.started_at(),
        counts=counts,
        session=sess,
    )
