"""Ignored jobs sheet endpoints."""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from api.auth import get_current_user
from api.database import get_db
from api.models import IgnoredJob, User
from api.schemas import IgnoredJobCreate, IgnoredJobRead, PaginatedIgnoredJobs
from core.ignored_jobs import add_ignored_job, mark_expired

router = APIRouter()


@router.get("/api/ignored-jobs", response_model=PaginatedIgnoredJobs)
def list_ignored_jobs(
    status: str = Query("active"),
    db: DBSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    mark_expired(db)
    q = db.query(IgnoredJob)
    if status and status != "all":
        q = q.filter(IgnoredJob.status == status)
    rows = q.order_by(IgnoredJob.ignored_at.desc(), IgnoredJob.id.desc()).all()
    return PaginatedIgnoredJobs(
        total=len(rows),
        records=[IgnoredJobRead.model_validate(r) for r in rows],
    )


@router.post("/api/ignored-jobs", response_model=IgnoredJobRead)
def create_ignored_job(
    body: IgnoredJobCreate,
    db: DBSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = add_ignored_job(
        db,
        platform=body.platform,
        company=body.company,
        title=body.job_title,
        url=body.job_url,
        reason=body.ignore_reason,
        score=body.score,
        ignore_type=body.ignore_type or "manual",
        expires_days=body.expires_days,
    )
    if row is None:
        raise HTTPException(400, "At least job URL or company/title is required")
    return row


@router.delete("/api/ignored-jobs/{ignore_id}")
def delete_ignored_job(
    ignore_id: int,
    db: DBSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = db.get(IgnoredJob, ignore_id)
    if not row:
        raise HTTPException(404, "Ignored job not found")
    row.status = "removed"
    db.commit()
    return {"status": "removed"}


@router.post("/api/ignored-jobs/clear-expired")
def clear_expired_ignored_jobs(
    db: DBSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    mark_expired(db)
    rows = db.query(IgnoredJob).filter(IgnoredJob.status == "expired").all()
    count = len(rows)
    for row in rows:
        db.delete(row)
    db.commit()
    return {"status": "cleared", "count": count}


@router.get("/api/ignored-jobs/export.csv")
def export_ignored_jobs(
    db: DBSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    mark_expired(db)
    rows = db.query(IgnoredJob).order_by(IgnoredJob.ignored_at.desc(), IgnoredJob.id.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "ignored_at", "platform", "company", "job_title", "job_url",
        "job_fingerprint", "ignore_type", "ignore_reason", "score",
        "status", "expires_at",
    ])
    for r in rows:
        writer.writerow([
            r.ignored_at or "", r.platform or "", r.company or "",
            r.job_title or "", r.job_url or "", r.job_fingerprint or "",
            r.ignore_type or "", r.ignore_reason or "", r.score or 0,
            r.status or "", r.expires_at or "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ignored_jobs.csv"},
    )
