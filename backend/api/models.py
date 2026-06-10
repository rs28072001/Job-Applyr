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
    ai_provider           = Column(String,  default="azure")  # azure | openai | gemini | grok
    openai_api_key        = Column(String,  default="")
    openai_model          = Column(String,  default="gpt-4o-mini")
    gemini_api_key        = Column(String,  default="")
    gemini_model          = Column(String,  default="gemini-2.5-flash")
    grok_api_key          = Column(String,  default="")
    grok_model            = Column(String,  default="grok-3-mini")
    confidence_threshold  = Column(Integer, default=75)
    port_num              = Column(Integer, default=9222)
    max_jobs_per_hour     = Column(Integer, default=30)
    max_jobs_per_day      = Column(Integer, default=150)
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
    external_site_url   = Column(String,  default="")
    matched_skills      = Column(JSON,    default=list)
    missing_skills      = Column(JSON,    default=list)
    status              = Column(String,  default="skipped")  # applied|skipped|skipped_external|error
    error_message       = Column(Text,    nullable=True)
    timestamp           = Column(DateTime, default=_now)
