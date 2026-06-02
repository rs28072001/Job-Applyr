"""SQLAlchemy engine, session factory, and DB initialisation."""
import os
from pathlib import Path
from sqlalchemy import create_engine
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

    db = SessionLocal()
    try:
        cfg = db.get(Config, 1)
        if cfg is None:
            db.add(Config(id=1))
            db.commit()
    finally:
        db.close()
