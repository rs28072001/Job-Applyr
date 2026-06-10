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


class SessionRead(BaseModel):
    id                  : int
    platform            : str
    mode                : str
    location            : str
    job_target          : int
    confidence_threshold: int
    keywords            : list[str]
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
    error_message      : Optional[str]
    timestamp          : datetime

    class Config:
        from_attributes = True


class PaginatedApplications(BaseModel):
    total   : int
    page    : int
    per_page: int
    records : list[ApplicationRead]
