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
    if "config" in inspector.get_table_names():
        existing = {column["name"] for column in inspector.get_columns("config")}
        with engine.begin() as conn:
            for name, default in _CONFIG_COLUMN_DEFAULTS.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE config ADD COLUMN {name} VARCHAR DEFAULT {default}"))
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
