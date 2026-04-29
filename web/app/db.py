from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


def create_engine(url: str | None = None, **kwargs: Any) -> Any:
    """Create an async engine with the given URL or default from settings."""
    db_url = url or settings.database_url
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_async_engine(db_url, connect_args=connect_args, **kwargs)


engine = create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
