"""SQLAlchemy engine, session factory, and DB initialisation."""
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./data/smart_job_assistant.db",
)

# Ensure the parent directory of the SQLite file exists before creating the engine
_db_path = DATABASE_URL.replace("sqlite:///", "")
if _db_path and not _db_path.startswith(":"):
    Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite in FastAPI
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


_CONFIG_COLUMN_DEFAULTS = {
    "keywords": "'[]'",
    "easy_apply_only": "1",
    "include_external_review": "1",
    "outreach_mode": "'draft_only'",
    "smtp_host": "''",
    "smtp_port": "587",
    "smtp_username": "''",
    "smtp_password": "''",
    "smtp_from": "''",
    "hide_previously_skipped": "1",
    "auto_ignore_skipped": "1",
    "date_posted_filter": "'any'",
    "naukri_search_mode": "'selenium'",
    "naukri_cookie": "''",
    "naukri_nkparam": "''",
    "naukri_auto_capture": "0",
    "ai_provider": "'azure'",
    "openai_api_key": "''",
    "openai_model": "'gpt-4o-mini'",
    "gemini_api_key": "''",
    "gemini_model": "'gemini-2.5-flash'",
    "groq_api_key": "''",
    "groq_model": "'openai/gpt-oss-120b'",
    "openrouter_api_key": "''",
    "openrouter_model": "'openai/gpt-oss-120b'",
    "openrouter_base_url": "'https://openrouter.ai/api/v1'",
}


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables and ensure the singleton config row exists."""
    from api.models import Config  # local import to avoid circular
    Base.metadata.create_all(engine)

    inspector = inspect(engine)

    _SESSION_COLUMN_DEFAULTS = {
        "easy_apply_only": "1",
        "include_external_review": "1",
        "outreach_mode": "'draft_only'",
        "hide_previously_skipped": "1",
        "auto_ignore_skipped": "1",
        "date_posted_filter": "'any'",
    }
    _APPLICATION_COLUMN_DEFAULTS = {
        "classification": "''",
        "failure_reason": "''",
        "recommendation": "''",
        "rationale": "''",
        "evidence_path": "''",
        "updated_at": "NULL",
    }
    for table, defaults in (("sessions", _SESSION_COLUMN_DEFAULTS),
                            ("applications", _APPLICATION_COLUMN_DEFAULTS)):
        if table in inspector.get_table_names():
            existing = {c["name"] for c in inspector.get_columns(table)}
            with engine.begin() as conn:
                for name, default in defaults.items():
                    if name not in existing:
                        conn.execute(text(
                            f"ALTER TABLE {table} ADD COLUMN {name} VARCHAR DEFAULT {default}"
                        ))
    # Migrate legacy application statuses to the new lifecycle vocabulary.
    if "applications" in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE applications SET status='manual_review', failure_reason='external_site' "
                "WHERE status='skipped_external'"
            ))
            conn.execute(text("UPDATE applications SET status='failed' WHERE status='error'"))
            # Skip-reason vocabulary rename (v3): clearer, user-facing names.
            conn.execute(text(
                "UPDATE applications SET failure_reason='low_score' WHERE failure_reason='below_threshold'"))
            conn.execute(text(
                "UPDATE applications SET failure_reason='ai_skip' WHERE failure_reason='llm_recommended_skip'"))
    if "ignored_jobs" in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE ignored_jobs SET status='expired' WHERE ignore_reason='title_mismatch'"
            ))
            # v4: external company-site jobs are auto-SAVED (no user action
            # requested). Lift previous external rows into the saved list.
            conn.execute(text(
                "UPDATE applications SET status='saved' "
                "WHERE failure_reason='external_site' AND status IN ('manual_review','skipped')"))

    if "config" in inspector.get_table_names():
        existing = {column["name"] for column in inspector.get_columns("config")}
        with engine.begin() as conn:
            for name, default in _CONFIG_COLUMN_DEFAULTS.items():
                if name not in existing:
                    # Boolean defaults ("0"/"1") need INTEGER affinity — on a
                    # TEXT/VARCHAR column SQLite stores False as the string '0',
                    # which Python reads back as truthy (bool('0') is True).
                    col_type = "INTEGER" if default in ("0", "1") else "VARCHAR"
                    conn.execute(text(f"ALTER TABLE config ADD COLUMN {name} {col_type} DEFAULT {default}"))
            if "grok_api_key" in existing and "groq_api_key" not in existing:
                conn.execute(text("UPDATE config SET groq_api_key = COALESCE(NULLIF(grok_api_key, ''), groq_api_key)"))
            if "grok_model" in existing and "groq_model" not in existing:
                conn.execute(text("UPDATE config SET groq_model = COALESCE(NULLIF(grok_model, ''), groq_model)"))
            conn.execute(text("UPDATE config SET ai_provider = 'groq' WHERE ai_provider = 'grok'"))

    db = SessionLocal()
    try:
        cfg = db.get(Config, 1)
        if cfg is None:
            db.add(Config(id=1))
            db.commit()
    finally:
        db.close()
