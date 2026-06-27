"""POST /api/system/reset — wipe job-search data, keep credentials.

Deletes sessions, applications, ignored jobs, outreach drafts/logs, audit events,
CV profiles, and uploaded resume/log files. Preserves the Config row (AI keys,
Naukri/LinkedIn credentials, preferences) and the user account.
"""
import os
import pathlib

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from api.auth import get_current_user
from api.database import get_db
from api.models import (
    User, Application, Session as SessionModel, IgnoredJob,
    OutreachDraft, OutreachSendLog, AuditEvent, CVProfile,
)

router = APIRouter()

CV_DIR = pathlib.Path(os.getenv("CV_UPLOAD_DIR", "./data/cv"))
LOGS_DIR = pathlib.Path("./logs")


@router.post("/api/system/reset")
def reset_job_data(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Clear all job-search data. Credentials and preferences are kept."""
    # Stop any running session first so the worker doesn't write rows back.
    import api.session_manager as sm
    if sm.is_running():
        sm.stop()

    deleted = {}
    # Order respects no hard FKs, but delete children first to be safe.
    for label, model in (
        ("outreach_send_log", OutreachSendLog),
        ("outreach_drafts", OutreachDraft),
        ("audit_events", AuditEvent),
        ("applications", Application),
        ("ignored_jobs", IgnoredJob),
        ("sessions", SessionModel),
        ("cv_profiles", CVProfile),
    ):
        deleted[label] = db.query(model).delete()
    db.commit()

    # Remove uploaded resume files + run logs (best-effort).
    files_removed = 0
    for directory in (CV_DIR, LOGS_DIR):
        if directory.exists():
            for f in directory.glob("*"):
                if f.is_file():
                    try:
                        f.unlink()
                        files_removed += 1
                    except OSError:
                        pass

    return {"status": "reset", "deleted": deleted, "files_removed": files_removed}
