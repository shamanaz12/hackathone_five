"""
TaskFlow AI Support Agent — Database Session Factory (SQLite Synchronous)
CRM Digital FTE Factory Final Hackathon 5

Provides:
- Synchronous Engine creation from settings
- session factory
- get_db() FastAPI dependency
- init_db() to create tables on startup
"""

from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from production.config.settings import get_settings
from production.database.models import Base

# Import all models
from production.database.models import (  # noqa: F401
    Customer,
    Ticket,
    Conversation,
    Message,
    Escalation,
    KnowledgeBase,
    IdentityMap,
    AuditLog,
    SystemConfig,
)

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Engine & Session Factory ──

_engine = None
_session_factory: sessionmaker[Session] | None = None


def get_engine():
    """Return the engine (created on first call)."""
    global _engine
    if _engine is None:
        # SQLite-specific config
        connect_args = {"check_same_thread": False} if "sqlite" in settings.database_url else {}
        _engine = create_engine(
            settings.database_url,
            echo=settings.debug,
            connect_args=connect_args
        )
        logger.info("Engine created for %s", settings.database_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the session factory (created on first call)."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: yield a session, then close.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables for SQLite."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("SQLite database tables ensured")


def close_db() -> None:
    """Cleanup on shutdown."""
    global _engine, _session_factory
    if _engine:
        _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed")
