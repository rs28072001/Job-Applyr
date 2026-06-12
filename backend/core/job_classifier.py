"""Classify a job BEFORE scoring/applying, and route the classification to a
pipeline decision. Pure functions — fully covered by tests.

Classifications:
  platform_easy_apply      — LinkedIn Easy Apply (platform-native flow)
  platform_internal_apply  — Naukri internal apply / chatbot flow
  external_ats             — "Apply on company site" → never auto-handled
  email_outreach_candidate — external job with a visible recruiter email
  manual_review            — needs a human (no apply button, ambiguous page)
  unsupported              — cannot be handled safely (login wall, challenge)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.page_signals import PageSignals
from core.statuses import AppStatus, FailureReason, JobClassification, OutreachMode


def classify_job(signals: PageSignals, outreach_mode: str = OutreachMode.DRAFT_ONLY) -> str:
    """Map page signals to one classification. Conservative by design."""
    if signals.captcha_or_challenge:
        return JobClassification.UNSUPPORTED
    if signals.requires_login:
        return JobClassification.UNSUPPORTED

    if signals.platform == "linkedin":
        if signals.has_easy_apply:
            return JobClassification.PLATFORM_EASY_APPLY
        if signals.has_external_apply:
            if signals.visible_emails and outreach_mode != OutreachMode.OFF:
                return JobClassification.EMAIL_OUTREACH_CANDIDATE
            return JobClassification.EXTERNAL_ATS
        return JobClassification.MANUAL_REVIEW

    if signals.platform == "naukri":
        # Naukri "Easy Apply" == internal apply / chatbot flow only.
        if signals.has_internal_apply and not signals.has_external_apply:
            return JobClassification.PLATFORM_INTERNAL_APPLY
        if signals.has_external_apply:
            if signals.visible_emails and outreach_mode != OutreachMode.OFF:
                return JobClassification.EMAIL_OUTREACH_CANDIDATE
            return JobClassification.EXTERNAL_ATS
        return JobClassification.MANUAL_REVIEW

    return JobClassification.UNSUPPORTED


@dataclass
class RouteDecision:
    """What the pipeline should do with a classified job."""
    action: str                       # "proceed" | "outreach" | "finalize"
    status: Optional[str] = None      # final status when action == "finalize"
    failure_reason: str = ""


#: Classifications the automation may apply to directly.
AUTO_APPLY_CLASSIFICATIONS = frozenset({
    JobClassification.PLATFORM_EASY_APPLY,
    JobClassification.PLATFORM_INTERNAL_APPLY,
})


def route_classification(
    classification: str,
    signals: PageSignals,
    *,
    easy_apply_only: bool = True,
    include_external_review: bool = True,
    outreach_mode: str = OutreachMode.DRAFT_ONLY,
    handle_external: bool = False,
) -> RouteDecision:
    """Decide the next pipeline step for a classified job.

    External/company-site jobs are SAVED automatically (status ``saved``) with
    their link — no user action is requested and the session never waits.
    They are never auto-driven through third-party ATS sites. If
    ``include_external_review`` is off they are skipped (still with the
    ``external_site`` reason, never silently).
    """
    if signals.already_applied:
        return RouteDecision("finalize", AppStatus.SKIPPED, FailureReason.ALREADY_APPLIED)

    if signals.captcha_or_challenge:
        return RouteDecision("finalize", AppStatus.FAILED, FailureReason.CAPTCHA_OR_CHALLENGE)

    if signals.requires_login:
        return RouteDecision("finalize", AppStatus.FAILED, FailureReason.LOGIN_REQUIRED)

    if classification in AUTO_APPLY_CLASSIFICATIONS:
        return RouteDecision("proceed")

    if classification == JobClassification.EMAIL_OUTREACH_CANDIDATE:
        if outreach_mode != OutreachMode.OFF:
            return RouteDecision("outreach")
        # Outreach disabled → treat exactly like an external job.
        classification = JobClassification.EXTERNAL_ATS

    if classification == JobClassification.EXTERNAL_ATS:
        if include_external_review or handle_external:
            return RouteDecision("finalize", AppStatus.SAVED, FailureReason.EXTERNAL_SITE)
        return RouteDecision("finalize", AppStatus.SKIPPED, FailureReason.EXTERNAL_SITE)

    if classification == JobClassification.MANUAL_REVIEW:
        return RouteDecision("finalize", AppStatus.MANUAL_REVIEW, FailureReason.APPLY_BUTTON_NOT_FOUND)

    return RouteDecision("finalize", AppStatus.FAILED, FailureReason.UNSUPPORTED_FLOW)
