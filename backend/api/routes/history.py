"""GET /api/history  ·  GET /api/history/sessions  ·  GET /api/history/sessions/{id}"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from api.database import get_db
from api.models import Session as SessionModel, Application
from api.schemas import PaginatedApplications, SessionRead

router = APIRouter()


@router.get("/api/history/sessions", response_model=list[SessionRead])
def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    db: DBSession = Depends(get_db),
):
    sessions = (
        db.query(SessionModel)
        .order_by(SessionModel.started_at.desc())
        .limit(limit)
        .all()
    )
    return sessions


@router.get("/api/history/sessions/{session_id}", response_model=SessionRead)
def get_session(session_id: int, db: DBSession = Depends(get_db)):
    sess = db.get(SessionModel, session_id)
    if not sess:
        from fastapi import HTTPException
        raise HTTPException(404, "Session not found")
    return sess


@router.get("/api/history", response_model=PaginatedApplications)
def list_applications(
    session_id : Optional[int]  = Query(None),
    platform   : Optional[str]  = Query(None),
    status     : Optional[str]  = Query(None),
    min_score  : Optional[int]  = Query(None, ge=0, le=100),
    page       : int = Query(1,  ge=1),
    per_page   : int = Query(50, ge=1, le=200),
    db         : DBSession = Depends(get_db),
):
    q = db.query(Application)
    if session_id is not None:
        q = q.filter(Application.session_id == session_id)
    if platform:
        q = q.filter(Application.platform == platform)
    if status:
        q = q.filter(Application.status == status)
    if min_score is not None:
        q = q.filter(Application.score >= min_score)

    total   = q.count()
    records = (
        q.order_by(Application.timestamp.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return PaginatedApplications(total=total, page=page, per_page=per_page, records=records)
