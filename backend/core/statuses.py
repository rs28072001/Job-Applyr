"""Canonical job lifecycle states, classifications, and failure reasons.

Single source of truth used by the pipeline, the API, and tests.
"""
from __future__ import annotations


# ── Application lifecycle statuses ───────────────────────────────────────────

class AppStatus:
    QUEUED        = "queued"
    FETCHING      = "fetching"
    SCORING       = "scoring"
    SKIPPED       = "skipped"
    APPLYING      = "applying"
    APPLIED       = "applied"
    #: Apply click succeeded and no login/challenge/error appeared, but the
    #: platform showed no explicit confirmation banner. Treated as a success
    #: for pacing/dedupe purposes; surfaced distinctly in the UI.
    APPLIED_PENDING = "applied_pending_confirmation"
    #: External company-site job stored automatically with its link — purely
    #: informational, the user applies whenever (and if) they want.
    SAVED         = "saved"
    MANUAL_REVIEW = "manual_review"   # shown in UI as "Needs Attention"
    EMAIL_DRAFTED = "email_drafted"
    EMAIL_SENT    = "email_sent"
    FAILED        = "failed"
    STOPPED       = "stopped"

    ALL = (
        QUEUED, FETCHING, SCORING, SKIPPED, APPLYING, APPLIED, APPLIED_PENDING,
        SAVED, MANUAL_REVIEW, EMAIL_DRAFTED, EMAIL_SENT, FAILED, STOPPED,
    )


#: States that never change again on their own (user actions excluded).
TERMINAL_STATUSES = frozenset({
    AppStatus.APPLIED, AppStatus.APPLIED_PENDING, AppStatus.SKIPPED,
    AppStatus.FAILED, AppStatus.STOPPED, AppStatus.EMAIL_SENT,
})

#: States a row may be in while the pipeline is actively working on it.
ACTIVE_STATUSES = frozenset({
    AppStatus.QUEUED, AppStatus.FETCHING, AppStatus.SCORING, AppStatus.APPLYING,
})

_COMMON_EXITS = {AppStatus.SKIPPED, AppStatus.FAILED, AppStatus.STOPPED,
                 AppStatus.MANUAL_REVIEW, AppStatus.SAVED}

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    AppStatus.QUEUED:        frozenset({AppStatus.FETCHING, AppStatus.SCORING} | _COMMON_EXITS),
    AppStatus.FETCHING:      frozenset({AppStatus.SCORING, AppStatus.EMAIL_DRAFTED} | _COMMON_EXITS),
    AppStatus.SCORING:       frozenset({AppStatus.APPLYING, AppStatus.EMAIL_DRAFTED} | _COMMON_EXITS),
    AppStatus.APPLYING:      frozenset({AppStatus.APPLIED, AppStatus.APPLIED_PENDING} | _COMMON_EXITS),
    AppStatus.MANUAL_REVIEW: frozenset({AppStatus.APPLIED, AppStatus.SKIPPED, AppStatus.EMAIL_DRAFTED, AppStatus.STOPPED}),
    AppStatus.SAVED:         frozenset({AppStatus.APPLIED, AppStatus.SKIPPED, AppStatus.EMAIL_DRAFTED}),
    AppStatus.EMAIL_DRAFTED: frozenset({AppStatus.EMAIL_SENT, AppStatus.SKIPPED, AppStatus.STOPPED}),
    AppStatus.EMAIL_SENT:    frozenset(),
    AppStatus.APPLIED:       frozenset(),
    AppStatus.APPLIED_PENDING: frozenset({AppStatus.APPLIED}),  # user/platform confirms later
    AppStatus.SKIPPED:       frozenset(),
    AppStatus.FAILED:        frozenset(),
    AppStatus.STOPPED:       frozenset(),
}


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status == to_status:
        return True
    return to_status in ALLOWED_TRANSITIONS.get(from_status, frozenset())


# ── Job classifications (assigned before scoring/applying) ──────────────────

class JobClassification:
    PLATFORM_EASY_APPLY      = "platform_easy_apply"       # LinkedIn Easy Apply
    PLATFORM_INTERNAL_APPLY  = "platform_internal_apply"   # Naukri internal apply / chatbot
    EXTERNAL_ATS             = "external_ats"              # "Apply on company site"
    EMAIL_OUTREACH_CANDIDATE = "email_outreach_candidate"  # external + visible recruiter email
    MANUAL_REVIEW            = "manual_review"
    UNSUPPORTED              = "unsupported"

    ALL = (
        PLATFORM_EASY_APPLY, PLATFORM_INTERNAL_APPLY, EXTERNAL_ATS,
        EMAIL_OUTREACH_CANDIDATE, MANUAL_REVIEW, UNSUPPORTED,
    )


# ── Failure reasons ──────────────────────────────────────────────────────────

class FailureReason:
    LOGIN_REQUIRED        = "login_required"
    APPLY_BUTTON_NOT_FOUND = "apply_button_not_found"
    EXTERNAL_SITE         = "external_site"
    CAPTCHA_OR_CHALLENGE  = "captcha_or_challenge"
    CONFIRMATION_MISSING  = "confirmation_missing"
    UNSUPPORTED_FLOW      = "unsupported_flow"
    # Supplementary (not in the core spec list but useful and explicit)
    RATE_LIMITED          = "rate_limited"
    SCORING_FAILED        = "scoring_failed"
    BROWSER_ERROR         = "browser_error"
    ALREADY_APPLIED       = "already_applied"
    BELOW_THRESHOLD       = "low_score"
    LLM_RECOMMENDED_SKIP  = "ai_skip"
    TITLE_MISMATCH        = "title_mismatch"
    SESSION_STOPPED       = "session_stopped"
    DUPLICATE_COMPANY     = "duplicate_company"
    DAILY_CAP_REACHED     = "daily_cap_reached"
    UNSUPPORTED           = "unsupported"
    IGNORED_PREVIOUS_SKIP = "ignored_previous_skip"
    POSTED_DATE_OUT_OF_RANGE = "posted_date_out_of_range"


# ── Outreach modes / draft states ────────────────────────────────────────────

class OutreachMode:
    OFF                = "off"
    DRAFT_ONLY         = "draft_only"          # default — recommended
    SEND_AFTER_APPROVAL = "send_after_approval"

    ALL = (OFF, DRAFT_ONLY, SEND_AFTER_APPROVAL)


class DraftStatus:
    DRAFT     = "draft"
    APPROVED  = "approved"
    SENT      = "sent"
    DISCARDED = "discarded"
