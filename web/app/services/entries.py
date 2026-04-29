from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select

from app.config import settings
from app.models import Entry

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


async def create_entry(
    session: AsyncSession,
    *,
    category: str,
    event_type: str,
    logged_by: str,
    occurred_at: datetime | None = None,
    amount: str | None = None,
    location: str | None = None,
    command: str | None = None,
    result: str | None = None,
    duration_min: int | None = None,
    distance_km: float | None = None,
    cost_usd: float | None = None,
    notes: str | None = None,
) -> Entry:
    """Create a new entry in the database."""
    now = datetime.now(UTC).replace(tzinfo=None)
    entry = Entry(
        category=category,
        event_type=event_type,
        occurred_at=occurred_at or now,
        logged_at=now,
        logged_by=logged_by,
        amount=amount,
        location=location,
        command=command,
        result=result,
        duration_min=duration_min,
        distance_km=distance_km,
        cost_usd=cost_usd,
        notes=notes,
        updated_at=now,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def get_entry_by_id(session: AsyncSession, entry_id: int) -> Entry | None:
    """Get an entry by ID (includes soft-deleted)."""
    result = await session.execute(select(Entry).where(Entry.id == entry_id))
    return result.scalar_one_or_none()


async def get_entries_for_date(
    session: AsyncSession,
    target_date: date | None = None,
) -> Sequence[Entry]:
    """Get all non-deleted entries for a specific date, reverse chronological."""
    tz = ZoneInfo(settings.timezone)
    if target_date is None:
        target_date = datetime.now(tz).date()

    # Convert local date to UTC datetime range
    start_local = datetime(target_date.year, target_date.month, target_date.day, tzinfo=tz)
    end_local = datetime(
        target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999, tzinfo=tz
    )
    start_utc = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc = end_local.astimezone(UTC).replace(tzinfo=None)

    result = await session.execute(
        select(Entry)
        .where(
            and_(
                Entry.occurred_at >= start_utc,
                Entry.occurred_at <= end_utc,
                Entry.deleted_at.is_(None),
            )
        )
        .order_by(Entry.occurred_at.desc())
    )
    return result.scalars().all()


async def update_entry(
    session: AsyncSession,
    entry: Entry,
    *,
    event_type: str | None = None,
    occurred_at: datetime | None = None,
    logged_by: str | None = None,
    amount: str | None = None,
    location: str | None = None,
    command: str | None = None,
    result: str | None = None,
    duration_min: int | None = None,
    distance_km: float | None = None,
    cost_usd: float | None = None,
    notes: str | None = None,
    clear_fields: list[str] | None = None,
) -> Entry:
    """Update an entry with the provided fields."""
    now = datetime.now(UTC).replace(tzinfo=None)
    clear_fields = clear_fields or []

    if event_type is not None:
        entry.event_type = event_type
    if occurred_at is not None:
        entry.occurred_at = occurred_at
    if logged_by is not None:
        entry.logged_by = logged_by
    if amount is not None or "amount" in clear_fields:
        entry.amount = amount
    if location is not None or "location" in clear_fields:
        entry.location = location
    if command is not None or "command" in clear_fields:
        entry.command = command
    if result is not None or "result" in clear_fields:
        entry.result = result
    if duration_min is not None or "duration_min" in clear_fields:
        entry.duration_min = duration_min
    if distance_km is not None or "distance_km" in clear_fields:
        entry.distance_km = distance_km
    if cost_usd is not None or "cost_usd" in clear_fields:
        entry.cost_usd = cost_usd
    if notes is not None or "notes" in clear_fields:
        entry.notes = notes

    entry.updated_at = now
    await session.flush()
    await session.refresh(entry)
    return entry


async def soft_delete_entry(session: AsyncSession, entry: Entry) -> Entry:
    """Soft-delete an entry by setting deleted_at."""
    entry.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    entry.updated_at = entry.deleted_at
    await session.flush()
    await session.refresh(entry)
    return entry


async def undelete_entry(session: AsyncSession, entry: Entry) -> Entry:
    """Restore a soft-deleted entry by clearing deleted_at."""
    entry.deleted_at = None
    entry.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await session.flush()
    await session.refresh(entry)
    return entry
