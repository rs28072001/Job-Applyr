"""Extract apply-flow signals from a job page's HTML.

Works on raw HTML strings so the exact same logic runs against
``driver.page_source`` in production and against static fixtures in tests.
No platform protections are probed or bypassed — this only reads what the
page already shows the logged-in (or anonymous) user.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.email_discovery import EmailFinding, extract_visible_emails

_LOGIN_PHRASES = (
    "login to apply", "register to apply", "login to view",
    "register to unlock", "sign in to apply", "join now to apply",
)
_CHALLENGE_PHRASES = (
    "captcha", "verify you are human", "unusual activity",
    "security check", "are you a robot", "access denied",
    "checking your browser",
)
_ALREADY_APPLIED_MARKERS = ("already-applied", "already applied")

# Naukri
_NAUKRI_INTERNAL_APPLY_RE = re.compile(
    r"""<(?:button|a)\b[^>]*(?:id\s*=\s*["']apply-button["']|class\s*=\s*["'][^"']*apply-button[^"']*["'])""",
    re.IGNORECASE,
)
_NAUKRI_EXTERNAL_APPLY_RE = re.compile(
    r"""<button\b[^>]*(?:id\s*=\s*["']company-site-button["']|class\s*=\s*["'][^"']*company-site-button[^"']*["'])""",
    re.IGNORECASE,
)
_NAUKRI_CHATBOT_RE = re.compile(r"chatbot_Drawer|chatbot_drawer", re.IGNORECASE)

# LinkedIn
_LI_EASY_APPLY_RE = re.compile(
    r"""jobs-apply-button|aria-label\s*=\s*["'][^"']*Easy Apply""",
    re.IGNORECASE,
)
_LI_EXTERNAL_APPLY_RE = re.compile(r"""aria-label\s*=\s*["'][^"']*Apply on company website""", re.IGNORECASE)

_TAG_STRIP_RE = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAGS_RE = re.compile(r"<[^>]+>")


@dataclass
class PageSignals:
    platform: str
    url: str = ""
    requires_login: bool = False
    captcha_or_challenge: bool = False
    already_applied: bool = False
    has_internal_apply: bool = False    # Naukri internal apply / chatbot flow
    has_easy_apply: bool = False        # LinkedIn Easy Apply
    has_external_apply: bool = False    # "Apply on company site/website"
    visible_emails: list[EmailFinding] = field(default_factory=list)


def _page_text(html_str: str) -> str:
    return _TAGS_RE.sub(" ", _TAG_STRIP_RE.sub(" ", html_str)).lower()


def signals_from_html(html_str: str, platform: str, url: str = "") -> PageSignals:
    text = _page_text(html_str)
    sig = PageSignals(platform=platform, url=url)

    sig.requires_login = any(p in text for p in _LOGIN_PHRASES) or "/nlogin" in url.lower()
    sig.captcha_or_challenge = any(p in text for p in _CHALLENGE_PHRASES)
    sig.already_applied = any(m in html_str.lower() for m in _ALREADY_APPLIED_MARKERS)
    sig.visible_emails = extract_visible_emails(html_str, source_url=url)

    if platform == "naukri":
        sig.has_external_apply = bool(_NAUKRI_EXTERNAL_APPLY_RE.search(html_str))
        internal = bool(_NAUKRI_INTERNAL_APPLY_RE.search(html_str)) or bool(_NAUKRI_CHATBOT_RE.search(html_str))
        # A page can show both ("apply-button" styling on the company-site
        # button) — external wins only if no dedicated internal button exists.
        sig.has_internal_apply = internal
    elif platform == "linkedin":
        sig.has_easy_apply = bool(_LI_EASY_APPLY_RE.search(html_str))
        sig.has_external_apply = bool(_LI_EXTERNAL_APPLY_RE.search(html_str))

    return sig


def signals_from_driver(driver, platform: str) -> PageSignals:
    """Build signals from a live Selenium session (same parser as fixtures)."""
    try:
        html_str = driver.page_source or ""
    except Exception:
        html_str = ""
    try:
        url = driver.current_url or ""
    except Exception:
        url = ""
    return signals_from_html(html_str, platform, url=url)
