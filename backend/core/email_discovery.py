"""Recruiter / HR email discovery from VISIBLE public page content only.

Hard rules (account-safe & privacy-safe):
  * Only emails present in visible page text or in visible ``mailto:`` links
    are extracted (job description, recruiter cards, contact blocks).
  * Content inside <script>, <style>, <noscript>, HTML comments, or hidden
    (display:none / visibility:hidden / hidden attr) elements is discarded.
  * No guessing, pattern-permutation, or lookup of non-displayed addresses.
"""
from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
MAILTO_RE = re.compile(r"""href\s*=\s*["']mailto:([^"'?]+)""", re.IGNORECASE)

# Strip non-visible regions before text extraction.
_INVISIBLE_BLOCK_RE = re.compile(
    r"<(script|style|noscript|template)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HIDDEN_ELEMENT_RE = re.compile(
    r"<([a-z][a-z0-9]*)\b[^>]*(?:style\s*=\s*[\"'][^\"']*(?:display\s*:\s*none|visibility\s*:\s*hidden)[^\"']*[\"']|\bhidden(?=[\s=>]))[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")

# Addresses that are never a recruiter contact.
_JUNK_LOCALPART = ("noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon")
_JUNK_DOMAINS = (
    "example.com", "example.org", "email.com", "domain.com",
    "naukri.com", "naukrigulf.com", "linkedin.com", "licdn.com",
    "sentry.io", "wixpress.com", "godaddy.com",
)
_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


@dataclass
class EmailFinding:
    email: str
    source: str           # "mailto" | "visible_text"
    source_url: str = ""  # page the address was found on
    context: str = ""     # short surrounding text snippet


def _visible_text(html_str: str) -> str:
    """Approximate the text a user actually sees on the page."""
    cleaned = _COMMENT_RE.sub(" ", html_str)
    cleaned = _INVISIBLE_BLOCK_RE.sub(" ", cleaned)
    # Repeat hidden-element stripping a few times to handle simple nesting.
    for _ in range(3):
        new = _HIDDEN_ELEMENT_RE.sub(" ", cleaned)
        if new == cleaned:
            break
        cleaned = new
    text = _TAG_RE.sub(" ", cleaned)
    return _html.unescape(text)


def _is_plausible(email: str) -> bool:
    email = email.strip().strip(".").lower()
    if not EMAIL_RE.fullmatch(email):
        return False
    local, _, domain = email.partition("@")
    if any(local.startswith(j) for j in _JUNK_LOCALPART):
        return False
    if domain in _JUNK_DOMAINS or any(domain.endswith("." + d) for d in _JUNK_DOMAINS):
        return False
    if email.endswith(_IMAGE_EXT):
        return False
    return True


def _context_for(text: str, email: str, width: int = 80) -> str:
    idx = text.lower().find(email.lower())
    if idx < 0:
        return ""
    start = max(0, idx - width)
    end = min(len(text), idx + len(email) + width)
    return " ".join(text[start:end].split())


def extract_visible_emails(html_str: str, source_url: str = "") -> list[EmailFinding]:
    """Extract recruiter/HR candidate emails from visible page content.

    Returns deduplicated findings, mailto links first (strongest signal),
    then addresses written in visible text.
    """
    findings: list[EmailFinding] = []
    seen: set[str] = set()

    # 1. mailto: links — visible, deliberate contact affordances.
    #    Only consider mailto links that are NOT inside stripped/hidden regions.
    visible_html = _COMMENT_RE.sub(" ", html_str)
    visible_html = _INVISIBLE_BLOCK_RE.sub(" ", visible_html)
    for _ in range(3):
        new = _HIDDEN_ELEMENT_RE.sub(" ", visible_html)
        if new == visible_html:
            break
        visible_html = new
    for m in MAILTO_RE.finditer(visible_html):
        email = _html.unescape(m.group(1)).strip().lower()
        if email not in seen and _is_plausible(email):
            seen.add(email)
            findings.append(EmailFinding(email=email, source="mailto", source_url=source_url))

    # 2. Addresses written out in visible text.
    text = _visible_text(html_str)
    for m in EMAIL_RE.finditer(text):
        email = m.group(0).strip().strip(".").lower()
        if email not in seen and _is_plausible(email):
            seen.add(email)
            findings.append(EmailFinding(
                email=email, source="visible_text", source_url=source_url,
                context=_context_for(text, email),
            ))

    return findings
