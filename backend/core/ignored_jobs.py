"""Persistent ignored-job helpers.

This keeps repeated stable skips out of future runs while preserving an
auditable, reversible local sheet for the user.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

from core.statuses import FailureReason


STABLE_AUTO_IGNORE_REASONS = {
    FailureReason.LLM_RECOMMENDED_SKIP,
    FailureReason.BELOW_THRESHOLD,
    FailureReason.DUPLICATE_COMPANY,
    FailureReason.UNSUPPORTED_FLOW,
    FailureReason.EXTERNAL_SITE,
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (value or "").lower())).strip()


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        path = parts.path.rstrip("/")
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))
    except Exception:
        return raw.split("?", 1)[0].rstrip("/")


def fingerprint(platform: str, company: str, title: str, url: str = "") -> str:
    clean_url = normalize_url(url)
    if clean_url:
        return f"url:{clean_url}"
    return "tc:{platform}:{company}:{title}".format(
        platform=normalize_text(platform),
        company=normalize_text(company),
        title=normalize_text(title),
    )


def title_company_fingerprint(platform: str, company: str, title: str) -> str:
    return fingerprint(platform, company, title, "")


def expiry_for(url: str, ignore_type: str = "auto_skip") -> datetime | None:
    if ignore_type == "manual":
        return None
    return now_utc() + timedelta(days=30 if normalize_url(url) else 14)


def mark_expired(db) -> int:
    from api.models import IgnoredJob

    rows = (db.query(IgnoredJob)
              .filter(IgnoredJob.status == "active")
              .filter(IgnoredJob.expires_at.isnot(None))
              .filter(IgnoredJob.expires_at <= now_utc())
              .all())
    for row in rows:
        row.status = "expired"
    if rows:
        db.commit()
    return len(rows)


def find_ignored_job(db, *, platform: str, company: str, title: str, url: str = ""):
    """Return an active ignore row by exact URL, then title/company fallback."""
    from api.models import IgnoredJob

    mark_expired(db)
    fingerprints = []
    url_fp = fingerprint(platform, company, title, url)
    if url_fp and url_fp.startswith("url:"):
        fingerprints.append(url_fp)
    fingerprints.append(title_company_fingerprint(platform, company, title))
    return (db.query(IgnoredJob)
              .filter(IgnoredJob.status == "active")
              .filter(IgnoredJob.job_fingerprint.in_(fingerprints))
              .order_by(IgnoredJob.id.desc())
              .first())


def add_ignored_job(
    db, *,
    platform: str,
    company: str,
    title: str,
    url: str,
    reason: str,
    score: int = 0,
    ignore_type: str = "auto_skip",
    expires_days: int | None = None,
):
    """Upsert an ignore row. Existing removed/expired rows are reactivated."""
    from api.models import IgnoredJob

    fp = fingerprint(platform, company, title, url)
    if not fp:
        return None
    expires_at = None if ignore_type == "manual" else expiry_for(url, ignore_type)
    if expires_days is not None:
        expires_at = now_utc() + timedelta(days=max(1, int(expires_days)))

    row = db.query(IgnoredJob).filter_by(job_fingerprint=fp).first()
    if row is None:
        row = IgnoredJob(job_fingerprint=fp)
        db.add(row)
    row.platform = platform or ""
    row.company = company or ""
    row.job_title = title or ""
    row.job_url = normalize_url(url)
    row.ignore_type = ignore_type or "auto_skip"
    row.ignore_reason = reason or ""
    row.score = int(score or 0)
    row.status = "active"
    row.expires_at = expires_at
    if not row.ignored_at:
        row.ignored_at = now_utc()
    db.commit()
    db.refresh(row)
    return row


def maybe_auto_ignore(db, app, *, enabled: bool = True):
    if not enabled:
        return None
    reason = app.failure_reason or ""
    if app.status != "skipped" or reason not in STABLE_AUTO_IGNORE_REASONS:
        return None
    return add_ignored_job(
        db,
        platform=app.platform,
        company=app.company,
        title=app.job_title,
        url=app.job_url,
        reason=reason,
        score=app.score or 0,
        ignore_type="auto_skip",
    )
