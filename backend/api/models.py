"""SQLAlchemy ORM models — User auth + app data."""
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, JSON,
)
from api.database import Base


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    """Application user — email/password authentication."""
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    email           = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name       = Column(String, default="")
    created_at      = Column(DateTime, default=_now)
    is_active       = Column(Boolean, default=True)


class Config(Base):
    """Single-row table that replaces the .env file.
    Always id=1 — created on first boot by init_db()."""
    __tablename__ = "config"

    id                    = Column(Integer, primary_key=True, default=1)
    naukri_email          = Column(String,  default="")
    naukri_password       = Column(String,  default="")
    linkedin_email        = Column(String,  default="")
    linkedin_password     = Column(String,  default="")
    azure_openai_endpoint = Column(String,  default="")
    azure_openai_api_key  = Column(String,  default="")
    azure_deployment_name = Column(String,  default="gpt-4o-mini")
    ai_provider           = Column(String,  default="azure")  # azure | openai | gemini | groq | openrouter
    openai_api_key        = Column(String,  default="")
    openai_model          = Column(String,  default="gpt-4o-mini")
    gemini_api_key        = Column(String,  default="")
    gemini_model          = Column(String,  default="gemini-2.5-flash")
    groq_api_key          = Column(String,  default="")
    groq_model            = Column(String,  default="openai/gpt-oss-120b")
    openrouter_api_key    = Column(String,  default="")
    openrouter_model      = Column(String,  default="openai/gpt-oss-120b")
    openrouter_base_url   = Column(String,  default="https://openrouter.ai/api/v1")
    confidence_threshold  = Column(Integer, default=75)
    port_num              = Column(Integer, default=9222)
    max_jobs_per_hour     = Column(Integer, default=30)
    max_jobs_per_day      = Column(Integer, default=150)
    # Job preferences
    platform              = Column(String,  default="naukri")  # naukri | linkedin | both
    mode                  = Column(String,  default="search_and_apply")  # search | search_and_apply
    location              = Column(String,  default="gurugram")
    keywords              = Column(JSON,    default=list)  # target job titles / keywords
    job_target            = Column(Integer, default=5)
    # Safer-automation defaults
    easy_apply_only         = Column(Boolean, default=True)   # platform-native flows only
    include_external_review = Column(Boolean, default=True)   # external jobs → review queue
    outreach_mode           = Column(String,  default="draft_only")  # off | draft_only | send_after_approval
    # Optional SMTP (only used in send_after_approval mode, after explicit approval)
    smtp_host             = Column(String, default="")
    smtp_port             = Column(Integer, default=587)
    smtp_username         = Column(String, default="")
    smtp_password         = Column(String,  default="")
    smtp_from             = Column(String,  default="")
    hide_previously_skipped = Column(Boolean, default=True)
    auto_ignore_skipped     = Column(Boolean, default=True)
    date_posted_filter      = Column(String,  default="any")
    naukri_search_mode      = Column(String,  default="selenium")  # selenium | api
    # API-mode auth tokens pasted from a logged-in browser (expire frequently).
    naukri_cookie           = Column(Text,    default="")
    naukri_nkparam          = Column(Text,    default="")
    # When on, the cookie/nkparam are captured automatically via a real browser
    # (Selenium CDP) instead of being pasted by hand.
    naukri_auto_capture     = Column(Boolean, default=False)
    updated_at            = Column(DateTime, default=_now, onupdate=_now)


class CVProfile(Base):
    """Parsed CV data.  is_active=True marks the current profile."""
    __tablename__ = "cv_profiles"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    name             = Column(String,  default="")
    email            = Column(String,  default="")
    phone            = Column(String,  default="")
    raw_text         = Column(Text,    default="")
    skills           = Column(JSON,    default=list)   # list[str]
    job_titles       = Column(JSON,    default=list)   # list[str]
    experience_years = Column(Float,   default=0.0)
    education        = Column(JSON,    default=list)   # list[str]
    summary          = Column(Text,    default="")
    pdf_path         = Column(String,  default="")
    created_at       = Column(DateTime, default=_now)
    is_active        = Column(Boolean, default=True)


class Session(Base):
    """One job-search run."""
    __tablename__ = "sessions"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    platform             = Column(String)              # naukri | linkedin | both
    mode                 = Column(String)              # search | search_and_apply
    location             = Column(String,  default="")
    job_target           = Column(Integer, default=10)
    confidence_threshold = Column(Integer, default=75)
    keywords             = Column(JSON,    default=list)
    easy_apply_only         = Column(Boolean, default=True)
    include_external_review = Column(Boolean, default=True)
    outreach_mode           = Column(String,  default="draft_only")
    hide_previously_skipped = Column(Boolean, default=True)
    auto_ignore_skipped     = Column(Boolean, default=True)
    date_posted_filter      = Column(String,  default="any")
    started_at           = Column(DateTime, default=_now)
    ended_at             = Column(DateTime, nullable=True)
    applied              = Column(Integer, default=0)
    skipped              = Column(Integer, default=0)
    errors               = Column(Integer, default=0)
    status               = Column(String,  default="running")  # running|completed|stopped|failed


class Application(Base):
    """One job analysed/applied within a session."""
    __tablename__ = "applications"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    session_id          = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    platform            = Column(String)
    job_title           = Column(String,  default="")
    company             = Column(String,  default="")
    job_url             = Column(String,  default="")
    score               = Column(Integer, default=0)
    location            = Column(String,  default="")
    experience_required = Column(String,  default="")
    salary              = Column(String,  default="")
    job_description     = Column(Text,    default="")
    key_skills          = Column(JSON,    default=list)
    about_company       = Column(Text,    default="")
    posted_date         = Column(String,  default="")
    applicants_count    = Column(String,  default="")
    openings            = Column(String,  default="")
    company_logo_url    = Column(String,  default="")
    rating              = Column(String,  default="")   # AmbitionBox AggregateRating, e.g. "3.9"
    reviews_count       = Column(String,  default="")   # AmbitionBox ReviewsCount, e.g. "24283"
    company_url         = Column(String,  default="")   # company / reviews page (staticUrl)
    external_site_url   = Column(String,  default="")
    matched_skills      = Column(JSON,    default=list)
    missing_skills      = Column(JSON,    default=list)
    # Lifecycle (see core/statuses.py):
    # queued|fetching|scoring|skipped|applying|applied|manual_review|
    # email_drafted|email_sent|failed|stopped
    status              = Column(String,  default="queued", index=True)
    # platform_easy_apply|platform_internal_apply|external_ats|
    # email_outreach_candidate|manual_review|unsupported
    classification      = Column(String,  default="")
    # login_required|apply_button_not_found|external_site|captcha_or_challenge|
    # confirmation_missing|unsupported_flow|...
    failure_reason      = Column(String,  default="")
    recommendation      = Column(String,  default="")   # LLM: apply | skip
    rationale           = Column(Text,    default="")   # LLM rationale
    error_message       = Column(Text,    nullable=True)
    evidence_path       = Column(String,  default="")   # failure evidence dir (screenshot + page text)
    timestamp           = Column(DateTime, default=_now)
    updated_at          = Column(DateTime, default=_now, onupdate=_now)


class IgnoredJob(Base):
    """Jobs that should be skipped in future sessions after a stable skip.

    The fingerprint prefers an exact URL when available, otherwise falls back
    to platform + normalized company + normalized title. Rows are local and
    reversible from the UI.
    """
    __tablename__ = "ignored_jobs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ignored_at      = Column(DateTime, default=_now, index=True)
    platform        = Column(String, default="", index=True)
    company         = Column(String, default="")
    job_title       = Column(String, default="")
    job_url         = Column(String, default="")
    job_fingerprint = Column(String, default="", unique=True, index=True)
    ignore_type     = Column(String, default="auto_skip")  # auto_skip | manual
    ignore_reason   = Column(String, default="")
    score           = Column(Integer, default=0)
    status          = Column(String, default="active")     # active | removed | expired
    expires_at      = Column(DateTime, nullable=True, index=True)


class OutreachDraft(Base):
    """A reviewed-before-send recruiter email draft.

    Emails are discovered ONLY from visible public job content. Drafts are
    never sent automatically — sending requires explicit user approval and
    outreach_mode == send_after_approval."""
    __tablename__ = "outreach_drafts"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    application_id   = Column(Integer, ForeignKey("applications.id"), nullable=True, index=True)
    session_id       = Column(Integer, ForeignKey("sessions.id"), nullable=True, index=True)
    recruiter_email  = Column(String,  default="")
    email_source     = Column(String,  default="")   # mailto | visible_text
    email_source_url = Column(String,  default="")   # page the address was found on
    subject          = Column(String,  default="")
    body             = Column(Text,    default="")
    status           = Column(String,  default="draft")  # draft|approved|sent|discarded
    created_at       = Column(DateTime, default=_now)
    updated_at       = Column(DateTime, default=_now, onupdate=_now)
    sent_at          = Column(DateTime, nullable=True)


class OutreachSendLog(Base):
    """Immutable audit trail: every approved send (SMTP or user-confirmed)."""
    __tablename__ = "outreach_send_log"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    draft_id        = Column(Integer, ForeignKey("outreach_drafts.id"), nullable=True)
    application_id  = Column(Integer, ForeignKey("applications.id"), nullable=True)
    session_id      = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    job_title       = Column(String, default="")
    company         = Column(String, default="")
    recipient       = Column(String, default="")
    subject         = Column(String, default="")
    method          = Column(String, default="smtp")   # smtp | user_mail_client
    sent_at         = Column(DateTime, default=_now)


class AuditEvent(Base):
    """Session audit log — append-only record of every meaningful action."""
    __tablename__ = "audit_events"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    session_id  = Column(Integer, ForeignKey("sessions.id"), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)
    event_type  = Column(String, default="")   # session_started|status_change|backoff|stop|...
    detail      = Column(JSON,   default=dict)
    created_at  = Column(DateTime, default=_now)
