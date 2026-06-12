"""Recruiter outreach drafting and (strictly gated) sending.

Defaults are safe:
  * outreach_mode defaults to "draft_only" — drafts are stored, NEVER sent.
  * Sending requires ALL of: mode == send_after_approval, an explicitly
    approved draft, and configured SMTP credentials.
"""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional

from core.statuses import DraftStatus, OutreachMode

logger = logging.getLogger(__name__)


class OutreachSendError(Exception):
    pass


_EMAIL_RE_SIMPLE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

#: Common provider hints surfaced by validation (Gmail needs an app password).
_PROVIDER_HINTS = {
    "smtp.gmail.com": "Gmail requires an App Password (Google Account → Security → App passwords); your normal password will not work.",
    "smtp.office365.com": "Outlook/365 may require an app password or SMTP AUTH to be enabled for the mailbox.",
}


def validate_smtp_settings(smtp_settings: dict) -> list[str]:
    """Static validation of SMTP/Gmail settings. Returns a list of problems
    (empty list == looks valid). Does not open any network connection."""
    problems: list[str] = []
    host = (smtp_settings.get("host") or "").strip()
    sender = (smtp_settings.get("from_address") or smtp_settings.get("username") or "").strip()
    username = (smtp_settings.get("username") or "").strip()
    port = smtp_settings.get("port")

    if not host:
        problems.append("SMTP host is empty.")
    if not sender:
        problems.append("From address is empty (set 'From' or username).")
    elif not _EMAIL_RE_SIMPLE.match(sender):
        problems.append(f"From address '{sender}' is not a valid email address.")
    try:
        port = int(port or 0)
        if port <= 0 or port > 65535:
            problems.append("SMTP port must be between 1 and 65535.")
        elif port == 465:
            problems.append("Port 465 (implicit SSL) is not supported — use 587 with STARTTLS.")
    except (TypeError, ValueError):
        problems.append("SMTP port must be a number.")
    if username and not smtp_settings.get("password"):
        problems.append("Username is set but password is empty.")
    if host in _PROVIDER_HINTS and not smtp_settings.get("password"):
        problems.append(_PROVIDER_HINTS[host])
    return problems


def send_test_email(smtp_settings: dict, to_address: str = "",
                    *, smtp_client_factory=smtplib.SMTP) -> str:
    """Send a single self-addressed test email to verify SMTP credentials.
    Returns the recipient on success; raises OutreachSendError with a clear
    message on any problem. Allowed in every outreach mode (it only ever
    emails the user's own address)."""
    problems = validate_smtp_settings(smtp_settings)
    if problems:
        raise OutreachSendError(" ".join(problems))

    sender = (smtp_settings.get("from_address") or smtp_settings.get("username") or "").strip()
    recipient = (to_address or sender).strip()
    if not _EMAIL_RE_SIMPLE.match(recipient):
        raise OutreachSendError(f"Test recipient '{recipient}' is not a valid email address.")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "Job Assistant — SMTP test"
    msg.set_content(
        "This is a test email from your local Job Assistant.\n"
        "If you received it, outreach sending is configured correctly.\n"
        "No outreach email is ever sent without your explicit approval."
    )

    host = smtp_settings["host"].strip()
    port = int(smtp_settings.get("port") or 587)
    username = (smtp_settings.get("username") or "").strip()
    password = smtp_settings.get("password") or ""

    try:
        with smtp_client_factory(host, port, timeout=20) as client:
            try:
                client.starttls()
            except Exception:
                pass
            if username:
                client.login(username, password)
            client.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        hint = _PROVIDER_HINTS.get(host, "")
        raise OutreachSendError(f"SMTP authentication failed: {e.smtp_error or e}. {hint}".strip())
    except OSError as e:
        raise OutreachSendError(f"Could not reach {host}:{port} — {e}")
    except Exception as e:
        raise OutreachSendError(f"SMTP test failed: {e}")
    return recipient


@dataclass
class DraftContent:
    subject: str
    body: str


_DRAFT_TEMPLATE = """Dear Hiring Team,

I came across the {job_title} opening at {company} and would love to be considered.
{experience_line}My core skills include {skills}, which align closely with what the role asks for.

I've attached my resume and would welcome the chance to discuss how I can contribute.
Job reference: {job_url}

Best regards,
{name}
{phone}{email_line}"""


def generate_outreach_draft(
    cv_data,
    job_title: str,
    company: str,
    job_url: str,
    llm=None,
) -> DraftContent:
    """Build a reviewed-by-human email draft. Uses the LLM when available,
    falls back to a clean template. Never sends anything."""
    name = (getattr(cv_data, "name", "") or "").strip() or "Candidate"
    skills = ", ".join((getattr(cv_data, "skills", None) or [])[:6]) or "the skills listed in my resume"
    years = getattr(cv_data, "experience_years", 0) or 0
    phone = (getattr(cv_data, "phone", "") or "").strip()
    email = (getattr(cv_data, "email", "") or "").strip()

    subject = f"Application for {job_title} — {name}"

    if llm is not None:
        try:
            body = llm.draft_outreach_email(job_title, company, job_url)
            if body and len(body.strip()) > 40:
                return DraftContent(subject=subject, body=body.strip())
        except Exception as e:  # template fallback — drafting must never fail hard
            logger.warning("LLM outreach draft failed, using template: %s", e)

    experience_line = f"I bring {years:g} years of relevant experience. " if years else ""
    body = _DRAFT_TEMPLATE.format(
        job_title=job_title, company=company or "your company",
        experience_line=experience_line, skills=skills, job_url=job_url,
        name=name, phone=phone,
        email_line=f"\n{email}" if email else "",
    )
    return DraftContent(subject=subject, body=body)


def send_outreach_email(
    draft,                      # api.models.OutreachDraft row
    outreach_mode: str,
    smtp_settings: dict,
    *,
    smtp_client_factory=smtplib.SMTP,
) -> None:
    """Send ONE approved draft. Raises OutreachSendError unless every safety
    gate passes. This is the only send path in the codebase."""
    if outreach_mode != OutreachMode.SEND_AFTER_APPROVAL:
        raise OutreachSendError(
            "Outreach mode is not 'send_after_approval' — sending is disabled."
        )
    if draft.status != DraftStatus.APPROVED:
        raise OutreachSendError("Draft must be explicitly approved before sending.")

    host = (smtp_settings.get("host") or "").strip()
    sender = (smtp_settings.get("from_address") or smtp_settings.get("username") or "").strip()
    if not host or not sender:
        raise OutreachSendError(
            "SMTP is not configured. Add SMTP settings, or copy the draft and send it from your own mail client."
        )

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = draft.recruiter_email
    msg["Subject"] = draft.subject
    msg.set_content(draft.body)

    port = int(smtp_settings.get("port") or 587)
    username = (smtp_settings.get("username") or "").strip()
    password = smtp_settings.get("password") or ""

    with smtp_client_factory(host, port, timeout=30) as client:
        try:
            client.starttls()
        except Exception:
            pass  # server may not support STARTTLS (e.g. local relay)
        if username:
            client.login(username, password)
        client.send_message(msg)
    logger.info("Outreach email sent to %s for draft %s", draft.recruiter_email, draft.id)
