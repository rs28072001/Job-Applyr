import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ApplicationRecord:
    platform: str
    job_title: str
    company: str
    job_url: str
    score: int
    matched_skills: list = field(default_factory=list)
    missing_skills: list = field(default_factory=list)
    status: str = "skipped"
    error_message: str = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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
    return [ApplicationRecord(**r) for r in _load_raw(log_path)]


def append_record(log_path: str, record: ApplicationRecord) -> None:
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    records = _load_raw(log_path)
    records.append(asdict(record))
    with p.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


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
