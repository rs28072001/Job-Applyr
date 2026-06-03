"""POST /api/session/start  ·  POST /api/session/stop  ·  GET /api/session/status"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from api.auth import get_current_user
from api.database import get_db
from api.models import Session as SessionModel, CVProfile, Config as ConfigModel, User
from api.schemas import SessionStartRequest, SessionStatus
import api.session_manager as sm

router = APIRouter()


@router.post("/api/session/start")
def start_session(body: SessionStartRequest, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    if sm.is_running():
        raise HTTPException(409, "A session is already running. Stop it first.")

    # Validate config is set up
    cfg = db.get(ConfigModel, 1)
    if not cfg or not cfg.azure_openai_endpoint:
        raise HTTPException(400, "LLM credentials not configured. Complete setup first.")

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
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)

    run_kwargs = {
        "platform": body.platform, "mode": body.mode, "location": body.location,
        "job_target": body.job_target, "confidence_threshold": body.confidence_threshold,
        "keywords": keywords,
    }
    sm.start(sess.id, run_kwargs)
    return {"status": "started", "session_id": sess.id}


@router.post("/api/session/stop")
def stop_session(_: User = Depends(get_current_user)):
    if not sm.is_running():
        raise HTTPException(400, "No session is currently running.")
    sm.stop()
    return {"status": "stopping"}


@router.get("/api/session/status", response_model=SessionStatus)
def session_status(_: User = Depends(get_current_user)):
    return SessionStatus(
        is_running=sm.is_running(),
        session_id=sm.current_session_id(),
        started_at=sm.started_at(),
    )
