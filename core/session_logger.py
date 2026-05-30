import csv
import json
from dataclasses import dataclass, asdict, field, fields as dc_fields
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ApplicationRecord:
    platform: str
    job_title: str
    company: str
    job_url: str
    score: int
    location: str = ""
    experience_required: str = ""
    job_description: str = ""
    key_skills: list = field(default_factory=list)
    about_company: str = ""
    external_site_url: str = ""
    matched_skills: list = field(default_factory=list)
    missing_skills: list = field(default_factory=list)
    status: str = "skipped"
    error_message: str = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_CSV_COLUMNS = [
    "timestamp",
    "platform",
    "company",
    "job_title",
    "location",
    "experience_required",
    "confidence",
    "job_status",
    "key_skills",
    "matched_skills",
    "missing_skills",
    "external_site_url",
    "about_company",
    "job_description",
    "job_url",
]

_ERROR_COLUMNS = [
    "timestamp",
    "platform",
    "company",
    "job_title",
    "job_url",
    "error_message",
]


def _record_to_csv_row(record: ApplicationRecord) -> dict:
    return {
        "timestamp": record.timestamp,
        "platform": record.platform,
        "company": record.company,
        "job_title": record.job_title,
        "location": record.location or "",
        "experience_required": record.experience_required or "",
        "confidence": record.score,
        "job_status": record.status,
        "key_skills": ", ".join(record.key_skills) if record.key_skills else "",
        "matched_skills": ", ".join(record.matched_skills) if record.matched_skills else "",
        "missing_skills": ", ".join(record.missing_skills) if record.missing_skills else "",
        "external_site_url": record.external_site_url or "",
        "about_company": record.about_company or "",
        "job_description": record.job_description or "",
        "job_url": record.job_url,
    }


def _load_raw(log_path: str) -> list:
    p = Path(log_path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    with p.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def load_log(log_path: str) -> list[ApplicationRecord]:
    valid_keys = {f.name for f in dc_fields(ApplicationRecord)}
    return [ApplicationRecord(**{k: v for k, v in r.items() if k in valid_keys}) for r in _load_raw(log_path)]


def append_record(log_path: str, record: ApplicationRecord) -> None:
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    records = _load_raw(log_path)
    records.append(asdict(record))
    with p.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def append_csv_row(csv_path: str, record: ApplicationRecord) -> None:
    """Append one row to the live CSV report, writing the header if the file is new."""
    p = Path(csv_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_header = not p.exists() or p.stat().st_size == 0
    with p.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(_record_to_csv_row(record))


def append_error_log(error_log_path: str, record: ApplicationRecord) -> None:
    """Append one row to the error log CSV — only if the record has status 'error'."""
    if record.status != "error":
        return
    p = Path(error_log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_header = not p.exists() or p.stat().st_size == 0
    with p.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_ERROR_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "timestamp": record.timestamp,
            "platform": record.platform,
            "company": record.company,
            "job_title": record.job_title,
            "job_url": record.job_url,
            "error_message": record.error_message or "",
        })


def is_already_applied(log_path: str, job_url: str) -> bool:
    for r in _load_raw(log_path):
        if r.get("job_url") == job_url and r.get("status") == "applied":
            return True
    return False


def get_session_summary(records: list[ApplicationRecord]) -> dict:
    applied = sum(1 for r in records if r.status == "applied")
    skipped = sum(1 for r in records if r.status in ("skipped", "skipped_external"))
    errors = sum(1 for r in records if r.status == "error")
    return {
        "total": len(records),
        "applied": applied,
        "skipped": skipped,
        "errors": errors,
    }
