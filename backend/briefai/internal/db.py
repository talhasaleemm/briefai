"""
Database module — sets up SQLAlchemy engine, session maker, base model, and FastAPI dependency.
"""
from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from briefai.config import settings

logger = logging.getLogger(__name__)

# SQLite connection args for multi-threaded/async environments
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

try:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        echo=False,  # Set to True for debugging SQL queries
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.critical("Failed to initialize database engine with URL '%s': %s", settings.DATABASE_URL, e)
    raise

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session context cleanly."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
