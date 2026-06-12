import os
import sys
import pathlib

import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def db():
    """Isolated in-memory SQLite session with all tables created."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import api.models  # noqa: F401 — register models on Base
    from api.database import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
