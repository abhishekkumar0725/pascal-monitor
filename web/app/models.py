from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Entry(Base):
    """Single wide table for all Pascal activity entries."""

    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    logged_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), default=datetime.utcnow
    )
    logged_by: Mapped[str] = mapped_column(Text, nullable=False)

    # Feeding fields
    amount: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Bathroom fields
    location: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Training fields
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Walk fields
    duration_min: Mapped[int | None] = mapped_column(nullable=True)
    distance_km: Mapped[float | None] = mapped_column(nullable=True)

    # Spending fields
    cost_usd: Mapped[float | None] = mapped_column(nullable=True)

    # Common fields
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        Index("ix_entries_occurred_at", "occurred_at"),
        Index("ix_entries_category_occurred_at", "category", "occurred_at"),
        Index("ix_entries_deleted_at", "deleted_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Entry id={self.id} category={self.category!r} "
            f"event_type={self.event_type!r} occurred_at={self.occurred_at}>"
        )
