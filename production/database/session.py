"""
TaskFlow AI Support Agent — Async Database Session Factory
CRM Digital FTE Factory Final Hackathon 5

Provides:
- AsyncEngine creation from settings
- async_session factory
- get_async_session() FastAPI dependency
- init_db() to create tables on startup
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from production.config.settings import get_settings
from production.database.models import Base

# Import all models so they register with Base.metadata
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

# ── Engine & Session Factory (module-level, lazy-init) ──

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    """Return the async engine (created on first call)."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_async_url,
            echo=settings.debug,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        logger.info("AsyncEngine created for %s", settings.database_async_url.replace(settings.postgres_password, "***"))
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory (created on first call)."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: yield an async session, then close.

    Usage:
        @app.post("/...")
        async def my_endpoint(db: AsyncSession = Depends(get_async_session)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables that don't already exist (idempotent)."""
    engine = get_engine()
    async with engine.begin() as conn:
        # Create sequences first (referenced by server_default in models)
        await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS customer_seq START 1"))
        await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS ticket_seq START 1"))
        await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS escalation_seq START 1"))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables and sequences ensured (create_all ran)")


async def close_db() -> None:
    """Dispose the engine (cleanup on shutdown)."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed")
