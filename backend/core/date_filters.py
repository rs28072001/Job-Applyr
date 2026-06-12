"""Date-posted filter helpers for platform listings/details."""
from __future__ import annotations

import re
from datetime import timedelta

from core.ignored_jobs import now_utc


FILTER_DAYS = {
    "24h": 1,
    "3d": 3,
    "7d": 7,
    "14d": 14,
}


def max_age_days(value: str) -> int | None:
    return FILTER_DAYS.get((value or "any").strip())


def is_within_posted_filter(posted_date: str, date_filter: str) -> bool:
    days = max_age_days(date_filter)
    if not days:
        return True
    age = posted_age_days(posted_date)
    # If a platform does not expose/parse a posted date, do not punish the job.
    if age is None:
        return True
    return age <= days


def posted_age_days(posted_date: str) -> int | None:
    text = (posted_date or "").strip().lower()
    if not text:
        return None
    if any(token in text for token in ("today", "just now", "few hour", "hour", "minute")):
        return 0
    if "yesterday" in text:
        return 1

    m = re.search(r"(\d+)\s*(day|week|month|year|d|w|mo|yr)s?", text)
    if not m:
        # Dates like 11 Jun are ambiguous without a year; keep them.
        return None
    value = int(m.group(1))
    unit = m.group(2)
    if unit in ("day", "d"):
        return value
    if unit in ("week", "w"):
        return value * 7
    if unit in ("month", "mo"):
        return value * 30
    if unit in ("year", "yr"):
        return value * 365
    return None


def linkedin_time_filter(date_filter: str) -> str:
    mapping = {
        "24h": "r86400",
        "3d": "r259200",
        "7d": "r604800",
        "14d": "r1209600",
    }
    return mapping.get((date_filter or "any").strip(), "")
