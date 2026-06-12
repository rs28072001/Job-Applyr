"""Selector health check.

Validates every selector fallback group in core.selectors against bundled DOM
snapshot fixtures (tests/fixtures/*.html), and summarizes live selector
incidents from recent application rows. Surfaced at /api/health/selectors and
as dashboard alerts.

The HTML matcher supports the simple-selector subset we actually use
(tag, #id, .class, [attr='v'], [attr*='v']); descendant combinators are
checked by their final segment.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field

from core.selectors import SELECTORS, TEXT_MARKERS

FIXTURE_DIR = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures"

#: Which fixture should satisfy which selector group (platform, purpose).
#: A group is "healthy" if AT LEAST ONE fallback matches its fixture snapshot.
EXPECTATIONS: list[tuple[str, str, str]] = [
    # (platform, purpose, fixture file)
    ("naukri",   "internal_apply_button", "naukri_internal_apply.html"),
    ("naukri",   "external_apply_button", "naukri_external_apply.html"),
    ("naukri",   "already_applied",       "naukri_already_applied.html"),
    ("naukri",   "apply_success",         "naukri_apply_success.html"),
    ("naukri",   "chatbot_drawer",        "naukri_chatbot.html"),
    ("naukri",   "login_form",            "naukri_login_page.html"),
    ("linkedin", "easy_apply_button",     "linkedin_easy_apply.html"),
    ("linkedin", "external_apply_button", "linkedin_external_apply.html"),
    ("linkedin", "login_form",            "linkedin_login_wall.html"),
]

TEXT_EXPECTATIONS: list[tuple[str, str]] = [
    ("login_required", "naukri_login_required.html"),
    ("challenge",      "naukri_challenge.html"),
]


@dataclass
class GroupHealth:
    platform: str
    purpose: str
    fixture: str
    ok: bool
    matched_selector: str = ""
    error: str = ""


@dataclass
class SelectorHealthReport:
    ok: bool
    groups: list[GroupHealth] = field(default_factory=list)
    broken: list[str] = field(default_factory=list)


# ── Minimal CSS-subset matcher over raw HTML ─────────────────────────────────

_SEGMENT_RE = re.compile(
    r"(?P<tag>[a-zA-Z][a-zA-Z0-9]*)?"
    r"(?P<rest>(?:#[\w\-]+|\.[\w\-]+|\[[^\]]+\]|:[\w\-()']+)*)$"
)
_PART_RE = re.compile(r"#[\w\-]+|\.[\w\-]+|\[[^\]]+\]|:[\w\-()'\*=\[\]]+")
_ATTR_RE = re.compile(r"\[\s*([\w\-]+)\s*(\*?=)\s*['\"]?([^'\"\]]*)['\"]?\s*\]")


def _tag_open_iter(html: str, tag: str | None):
    """Yield every opening-tag string for `tag` (or any tag if None)."""
    pat = re.compile(rf"<{tag or '[a-zA-Z][a-zA-Z0-9]*'}\b[^>]*>", re.IGNORECASE)
    for m in pat.finditer(html):
        yield m.group(0)


def _attr_value(tag_html: str, attr: str) -> str | None:
    m = re.search(rf"""\b{re.escape(attr)}\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))""",
                  tag_html, re.IGNORECASE)
    if not m:
        return None
    return m.group(2) if m.group(2) is not None else (
        m.group(3) if m.group(3) is not None else m.group(4))


def html_matches_selector(html: str, selector: str) -> bool:
    """True if the final simple segment of `selector` matches any tag in html."""
    # Final segment only — split on whitespace that is NOT inside [brackets]
    segments = re.split(r"\s+(?![^\[]*\])", selector.strip())
    segment = segments[-1]
    m = _SEGMENT_RE.match(segment)
    if not m:
        return False
    tag = m.group("tag")
    parts = _PART_RE.findall(m.group("rest") or "")

    for tag_html in _tag_open_iter(html, tag):
        ok = True
        for part in parts:
            if part.startswith(":"):
                continue  # pseudo-classes (:not etc.) — skip in static check
            if part.startswith("#"):
                if (_attr_value(tag_html, "id") or "") != part[1:]:
                    ok = False; break
            elif part.startswith("."):
                classes = (_attr_value(tag_html, "class") or "").split()
                if part[1:] not in classes:
                    ok = False; break
            else:
                am = _ATTR_RE.match(part)
                if not am:
                    ok = False; break
                attr, op, val = am.group(1), am.group(2), am.group(3)
                actual = _attr_value(tag_html, attr)
                if actual is None:
                    ok = False; break
                if op == "=" and actual != val:
                    ok = False; break
                if op == "*=" and val not in actual:
                    ok = False; break
        if ok:
            return True
    return False


# ── Health check ─────────────────────────────────────────────────────────────

def run_selector_health_check(fixture_dir: pathlib.Path = FIXTURE_DIR) -> SelectorHealthReport:
    report = SelectorHealthReport(ok=True)

    for platform, purpose, fixture in EXPECTATIONS:
        path = fixture_dir / fixture
        gh = GroupHealth(platform=platform, purpose=purpose, fixture=fixture, ok=False)
        if not path.exists():
            gh.error = "fixture missing"
        else:
            html = path.read_text(encoding="utf-8")
            for sel in SELECTORS.get(platform, {}).get(purpose, []):
                if html_matches_selector(html, sel):
                    gh.ok = True
                    gh.matched_selector = sel
                    break
            if not gh.ok:
                gh.error = "no fallback selector matched fixture snapshot"
        report.groups.append(gh)
        if not gh.ok:
            report.ok = False
            report.broken.append(f"{platform}/{purpose}")

    for marker, fixture in TEXT_EXPECTATIONS:
        path = fixture_dir / fixture
        gh = GroupHealth(platform="text", purpose=marker, fixture=fixture, ok=False)
        if not path.exists():
            gh.error = "fixture missing"
        else:
            text = re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8")).lower()
            for phrase in TEXT_MARKERS.get(marker, []):
                if phrase in text:
                    gh.ok = True
                    gh.matched_selector = phrase
                    break
            if not gh.ok:
                gh.error = "no text marker matched fixture snapshot"
        report.groups.append(gh)
        if not gh.ok:
            report.ok = False
            report.broken.append(f"text/{marker}")

    return report


#: failure reasons that strongly indicate selector drift on live pages
SELECTOR_FAILURE_REASONS = ("apply_button_not_found", "confirmation_missing", "unsupported_flow")


def live_selector_incidents(db, hours: int = 24) -> dict[str, int]:
    """Count selector-related failures from persisted rows (last N hours)."""
    from datetime import datetime, timedelta, timezone
    from api.models import Application

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (db.query(Application)
              .filter(Application.timestamp >= since)
              .filter(Application.failure_reason.in_(SELECTOR_FAILURE_REASONS))
              .all())
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.failure_reason] = counts.get(r.failure_reason, 0) + 1
    return counts
