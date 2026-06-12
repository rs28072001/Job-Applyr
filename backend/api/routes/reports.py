"""Observability endpoints.

GET /api/health/selectors         — fixture-based selector health + live incidents
GET /api/alerts                   — actionable dashboard alerts
GET /api/sessions/{id}/audit      — session audit log
GET /api/sessions/{id}/report     — run report (JSON)
GET /api/sessions/{id}/report.csv — run report (CSV download)
"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from api.auth import get_current_user
from api.database import get_db
from api.models import (
    Application, AuditEvent, Config as ConfigModel, OutreachDraft,
    Session as SessionModel, User,
)
from core.outreach import validate_smtp_settings
from core.selector_health import live_selector_incidents, run_selector_health_check
from core.statuses import AppStatus, OutreachMode

router = APIRouter()


@router.get("/api/health/selectors")
def selector_health(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    report = run_selector_health_check()
    return {
        "ok": report.ok,
        "broken": report.broken,
        "groups": [{
            "platform": g.platform, "purpose": g.purpose, "fixture": g.fixture,
            "ok": g.ok, "matched_selector": g.matched_selector, "error": g.error,
        } for g in report.groups],
        "live_incidents_24h": live_selector_incidents(db, hours=24),
    }


@router.get("/api/alerts")
def alerts(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Actionable alerts for the dashboard."""
    out: list[dict] = []

    # 1) Broken selectors (static snapshot check + live incident spike)
    report = run_selector_health_check()
    if not report.ok:
        out.append({
            "id": "selectors_broken",
            "severity": "error",
            "title": "Selector health check failing",
            "detail": f"Broken groups: {', '.join(report.broken)}. "
                      "Apply automation may misfire — affected jobs are marked Needs Attention with a reason.",
        })
    incidents = live_selector_incidents(db, hours=24)
    incident_total = sum(incidents.values())
    if incident_total >= 3:
        out.append({
            "id": "selector_incidents",
            "severity": "warning",
            "title": f"{incident_total} selector-related failures in the last 24h",
            "detail": ", ".join(f"{k}: {v}" for k, v in incidents.items())
                      + ". Platform pages may have changed — see Skipped / Needs Attention.",
        })

    # 2) Missing/invalid SMTP while send-after-approval is on
    cfg = db.get(ConfigModel, 1)
    if cfg and (getattr(cfg, "outreach_mode", "") == OutreachMode.SEND_AFTER_APPROVAL):
        problems = validate_smtp_settings({
            "host": cfg.smtp_host, "port": cfg.smtp_port,
            "username": cfg.smtp_username, "password": cfg.smtp_password,
            "from_address": cfg.smtp_from,
        })
        if problems:
            out.append({
                "id": "smtp_missing",
                "severity": "warning",
                "title": "Outreach mode is 'send after approval' but SMTP is not ready",
                "detail": " ".join(problems) + " Approved drafts cannot be sent until this is fixed.",
            })

    # 3) High failure rate in the latest session
    sess = db.query(SessionModel).order_by(SessionModel.id.desc()).first()
    if sess:
        rows = db.query(Application).filter_by(session_id=sess.id).all()
        total = len(rows)
        failed = sum(1 for r in rows if r.status == AppStatus.FAILED)
        if total >= 5 and failed / total >= 0.3:
            out.append({
                "id": "high_failure_rate",
                "severity": "error",
                "title": f"High failure rate in last session ({failed}/{total} failed)",
                "detail": "Check failure reasons in History and the evidence captures before running again.",
            })

    return {"alerts": out}


@router.get("/api/sessions/{session_id}/audit")
def session_audit(session_id: int, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    if not db.get(SessionModel, session_id):
        raise HTTPException(404, "Session not found")
    events = (db.query(AuditEvent)
                .filter_by(session_id=session_id)
                .order_by(AuditEvent.id.asc())
                .limit(2000).all())
    return [{
        "id": e.id, "application_id": e.application_id,
        "event_type": e.event_type, "detail": e.detail, "created_at": e.created_at,
    } for e in events]


def _report_payload(session_id: int, db: DBSession) -> dict:
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    rows = (db.query(Application).filter_by(session_id=session_id)
              .order_by(Application.id.asc()).all())
    drafts = db.query(OutreachDraft).filter_by(session_id=session_id).all()
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {
        "session": {
            "id": sess.id, "platform": sess.platform, "mode": sess.mode,
            "location": sess.location, "job_target": sess.job_target,
            "confidence_threshold": sess.confidence_threshold,
            "easy_apply_only": getattr(sess, "easy_apply_only", True),
            "outreach_mode": getattr(sess, "outreach_mode", "draft_only"),
            "started_at": sess.started_at, "ended_at": sess.ended_at,
            "status": sess.status,
        },
        "totals": {"jobs": len(rows), "by_status": by_status,
                   "applied": sess.applied, "skipped": sess.skipped,
                   "failed": sess.errors, "drafts": len(drafts)},
        "applications": [{
            "id": r.id, "title": r.job_title, "company": r.company,
            "url": r.job_url, "platform": r.platform, "score": r.score,
            "status": r.status, "classification": r.classification,
            "failure_reason": r.failure_reason, "recommendation": r.recommendation,
            "rationale": r.rationale, "error": r.error_message,
            "evidence_path": r.evidence_path, "timestamp": r.timestamp,
        } for r in rows],
        "_rows": rows,   # ORM rows for the CSV exporter (not serialized)
    }


#: Exact export schema (order matters; missing values become empty strings).
CSV_COLUMNS = [
    "timestamp", "platform", "company", "company_logo_url", "job_title",
    "location", "experience_required", "salary", "confidence", "job_status",
    "posted_date", "openings", "applicants_count", "key_skills",
    "matched_skills", "missing_skills", "external_site_url", "about_company",
    "job_description", "job_url",
]


def _csv_value(value) -> str:
    """Empty string for missing values; join lists; stringify the rest."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v is not None and str(v).strip())
    return str(value)


def application_csv_row(r) -> list[str]:
    # 'confidence' is the LLM score — blank when the job was never scored.
    confidence = "" if not (r.recommendation or "").strip() and not r.score else r.score
    return [_csv_value(v) for v in [
        r.timestamp, r.platform, r.company, r.company_logo_url, r.job_title,
        r.location, r.experience_required, r.salary, confidence, r.status,
        r.posted_date, r.openings, r.applicants_count, r.key_skills,
        r.matched_skills, r.missing_skills, r.external_site_url,
        r.about_company, r.job_description, r.job_url,
    ]]


@router.get("/api/sessions/{session_id}/report")
def session_report(session_id: int, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    payload = _report_payload(session_id, db)
    payload.pop("_rows", None)
    return payload


@router.get("/api/sessions/{session_id}/report.csv")
def session_report_csv(session_id: int, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    payload = _report_payload(session_id, db)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for r in payload["_rows"]:
        writer.writerow(application_csv_row(r))
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition":
                 f"attachment; filename=session_{session_id}_report.csv"},
    )
