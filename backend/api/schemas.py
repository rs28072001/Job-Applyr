"""Pydantic schemas for request/response validation."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Config ────────────────────────────────────────────────────────────────────

class ConfigRead(BaseModel):
    naukri_email          : str = ""
    naukri_password       : str = ""   # masked to "***" by route
    linkedin_email        : str = ""
    linkedin_password     : str = ""   # masked to "***" by route
    azure_openai_endpoint : str = ""
    azure_openai_api_key  : str = ""   # masked to "***" by route
    azure_deployment_name : str = "gpt-4o-mini"
    ai_provider           : str = "azure"
    openai_api_key        : str = ""   # masked to "***" by route
    openai_model          : str = "gpt-4o-mini"
    gemini_api_key        : str = ""   # masked to "***" by route
    gemini_model          : str = "gemini-2.5-flash"
    groq_api_key          : str = ""   # masked to "***" by route
    groq_model            : str = "openai/gpt-oss-120b"
    openrouter_api_key    : str = ""   # masked to "***" by route
    openrouter_model      : str = "openai/gpt-oss-120b"
    openrouter_base_url   : str = "https://openrouter.ai/api/v1"
    confidence_threshold  : int = 75
    port_num              : int = 9222
    max_jobs_per_hour     : int = 30
    max_jobs_per_day      : int = 150
    easy_apply_only         : bool = True
    include_external_review : bool = True
    outreach_mode           : str = "draft_only"   # off | draft_only | send_after_approval
    smtp_host             : str = ""
    smtp_port             : int = 587
    smtp_username         : str = ""
    smtp_password         : str = ""   # masked to "***" by route
    smtp_from             : str = ""
    hide_previously_skipped : bool = True
    auto_ignore_skipped     : bool = True
    date_posted_filter      : str = "any"
    naukri_search_mode      : str = "selenium"  # selenium | api
    is_configured         : bool = False  # True when all required fields set

    class Config:
        from_attributes = True


class ConfigUpdate(BaseModel):
    naukri_email          : Optional[str] = None
    naukri_password       : Optional[str] = None
    linkedin_email        : Optional[str] = None
    linkedin_password     : Optional[str] = None
    azure_openai_endpoint : Optional[str] = None
    azure_openai_api_key  : Optional[str] = None
    azure_deployment_name : Optional[str] = None
    ai_provider           : Optional[str] = None
    openai_api_key        : Optional[str] = None
    openai_model          : Optional[str] = None
    gemini_api_key        : Optional[str] = None
    gemini_model          : Optional[str] = None
    groq_api_key          : Optional[str] = None
    groq_model            : Optional[str] = None
    openrouter_api_key    : Optional[str] = None
    openrouter_model      : Optional[str] = None
    openrouter_base_url   : Optional[str] = None
    confidence_threshold  : Optional[int] = Field(None, ge=0, le=100)
    port_num              : Optional[int] = None
    max_jobs_per_hour     : Optional[int] = None
    max_jobs_per_day      : Optional[int] = None
    platform              : Optional[str] = Field(None, pattern="^(naukri|linkedin|both)$")
    mode                  : Optional[str] = Field(None, pattern="^(search|search_and_apply)$")
    location              : Optional[str] = None
    job_target            : Optional[int] = None
    easy_apply_only         : Optional[bool] = None
    include_external_review : Optional[bool] = None
    outreach_mode           : Optional[str] = Field(None, pattern="^(off|draft_only|send_after_approval)$")
    smtp_host             : Optional[str] = None
    smtp_port             : Optional[int] = None
    smtp_username         : Optional[str] = None
    smtp_password         : Optional[str] = None
    smtp_from             : Optional[str] = None
    hide_previously_skipped : Optional[bool] = None
    auto_ignore_skipped     : Optional[bool] = None
    date_posted_filter      : Optional[str] = Field(None, pattern="^(any|24h|3d|7d|14d)$")
    naukri_search_mode      : Optional[str] = Field(None, pattern="^(selenium|api)$")


class ConfigTestRequest(ConfigUpdate):
    pass


class ConfigTestResponse(BaseModel):
    ok        : bool
    provider  : str
    model     : str
    output    : str = ""
    error     : str = ""


# ── CV Profile ────────────────────────────────────────────────────────────────

class CVProfileRead(BaseModel):
    id              : int
    name            : str
    email           : str
    phone           : str
    skills          : list[str]
    job_titles      : list[str]
    experience_years: float
    education       : list[str]
    summary         : str
    pdf_path        : str
    created_at      : datetime
    is_active       : bool

    class Config:
        from_attributes = True


class CVProfileUpdate(BaseModel):
    name            : Optional[str]  = None
    email           : Optional[str]  = None
    phone           : Optional[str]  = None
    skills          : Optional[list[str]] = None
    job_titles      : Optional[list[str]] = None
    experience_years: Optional[float] = None
    education       : Optional[list[str]] = None
    summary         : Optional[str]  = None


# ── Session ───────────────────────────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    platform            : str = "naukri"   # naukri | linkedin | both
    mode                : str = "search_and_apply"
    location            : str = "India"
    job_target          : int = Field(10, ge=1, le=100)
    confidence_threshold: int = Field(75, ge=0, le=100)
    keywords            : list[str] = []
    easy_apply_only         : bool = True   # platform-native flows only (default ON)
    include_external_review : bool = True   # external jobs → review queue, never silent
    outreach_mode           : str = Field("draft_only", pattern="^(off|draft_only|send_after_approval)$")
    hide_previously_skipped : bool = True
    auto_ignore_skipped     : bool = True
    date_posted_filter      : str = Field("any", pattern="^(any|24h|3d|7d|14d)$")


class SessionRead(BaseModel):
    id                  : int
    platform            : str
    mode                : str
    location            : str
    job_target          : int
    confidence_threshold: int
    keywords            : list[str]
    easy_apply_only         : bool = True
    include_external_review : bool = True
    outreach_mode           : str = "draft_only"
    hide_previously_skipped : bool = True
    auto_ignore_skipped     : bool = True
    date_posted_filter      : str = "any"
    started_at          : datetime
    ended_at            : Optional[datetime]
    applied             : int
    skipped             : int
    errors              : int
    status              : str

    class Config:
        from_attributes = True


class SessionStatus(BaseModel):
    is_running  : bool
    session_id  : Optional[int]
    started_at  : Optional[datetime]
    # Counters derived from PERSISTED application rows (never in-memory only)
    counts      : dict[str, int] = {}
    session     : Optional[SessionRead] = None


# ── Application ───────────────────────────────────────────────────────────────

class ApplicationRead(BaseModel):
    id                 : int
    session_id         : Optional[int]
    platform           : str
    job_title          : str
    company            : str
    job_url            : str
    score              : int
    location           : str
    experience_required: str
    salary             : str
    key_skills         : list[str]
    matched_skills     : list[str]
    missing_skills     : list[str]
    external_site_url  : str
    status             : str
    classification    : str = ""
    failure_reason    : str = ""
    recommendation    : str = ""
    rationale         : str = ""
    job_description   : str = ""
    error_message      : Optional[str]
    timestamp          : datetime
    updated_at         : Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedApplications(BaseModel):
    total   : int
    page    : int
    per_page: int
    records : list[ApplicationRead]


# ── Outreach & Review queue ──────────────────────────────────────────────────

class OutreachDraftRead(BaseModel):
    id               : int
    application_id   : Optional[int]
    session_id       : Optional[int]
    recruiter_email  : str
    email_source     : str
    email_source_url : str
    subject          : str
    body             : str
    status           : str          # draft | approved | sent | discarded
    created_at       : datetime
    updated_at       : Optional[datetime] = None
    sent_at          : Optional[datetime] = None
    job_title        : str = ""     # joined from application
    company          : str = ""
    job_url          : str = ""

    class Config:
        from_attributes = True


class OutreachDraftUpdate(BaseModel):
    subject : Optional[str] = None
    body    : Optional[str] = None


class ReviewQueueResponse(BaseModel):
    manual_review : list[ApplicationRead]            # "Needs Attention" in UI
    drafts        : list[OutreachDraftRead]
    skipped       : list[ApplicationRead] = []       # recent skips with reasons
    saved         : list[ApplicationRead] = []       # auto-saved external jobs


class ReviewResolveRequest(BaseModel):
    action : str = Field(..., pattern="^(mark_applied|dismiss)$")


class SmtpTestRequest(BaseModel):
    """Optional overrides so 'Send test email' works before saving config."""
    to          : Optional[str] = None   # defaults to the From address
    host        : Optional[str] = None
    port        : Optional[int] = None
    username    : Optional[str] = None
    password    : Optional[str] = None
    from_address: Optional[str] = None


# ── Ignored Jobs ─────────────────────────────────────────────────────────────

class IgnoredJobRead(BaseModel):
    id              : int
    ignored_at      : datetime
    platform        : str
    company         : str
    job_title       : str
    job_url         : str
    job_fingerprint : str
    ignore_type     : str
    ignore_reason   : str
    score           : int
    status          : str
    expires_at      : Optional[datetime]

    class Config:
        from_attributes = True


class IgnoredJobCreate(BaseModel):
    platform      : str = ""
    company       : str = ""
    job_title     : str = ""
    job_url       : str = ""
    ignore_type   : str = "manual"
    ignore_reason : str = "manual"
    score         : int = 0
    expires_days  : Optional[int] = None


class PaginatedIgnoredJobs(BaseModel):
    total   : int
    records : list[IgnoredJobRead]
