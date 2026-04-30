from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select

from app.config import settings
from app.models import Entry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_category_counts(
    session: AsyncSession,
    target_date: date | None = None,
) -> dict[str, int]:
    """Get counts per category for a specific date."""
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
        select(Entry.category, func.count(Entry.id))
        .where(
            and_(
                Entry.occurred_at >= start_utc,
                Entry.occurred_at <= end_utc,
                Entry.deleted_at.is_(None),
            )
        )
        .group_by(Entry.category)
    )

    counts: dict[str, int] = {}
    for category, count in result.all():
        counts[category] = count

    return counts


async def get_event_counts(
    session: AsyncSession,
    target_date: date | None = None,
) -> dict[str, int]:
    """Get counts per event_type for a specific date."""
    tz = ZoneInfo(settings.timezone)
    if target_date is None:
        target_date = datetime.now(tz).date()

    start_local = datetime(target_date.year, target_date.month, target_date.day, tzinfo=tz)
    end_local = datetime(
        target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999, tzinfo=tz
    )
    start_utc = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc = end_local.astimezone(UTC).replace(tzinfo=None)

    result = await session.execute(
        select(Entry.event_type, func.count(Entry.id))
        .where(
            and_(
                Entry.occurred_at >= start_utc,
                Entry.occurred_at <= end_utc,
                Entry.deleted_at.is_(None),
            )
        )
        .group_by(Entry.event_type)
    )

    counts: dict[str, int] = {}
    for event_type, count in result.all():
        counts[event_type] = count

    return counts


async def get_last_event(
    session: AsyncSession,
    category: str | None = None,
    event_type: str | None = None,
) -> Entry | None:
    """Get the most recent event of a given category or event_type."""
    query = select(Entry).where(Entry.deleted_at.is_(None))

    if category:
        query = query.where(Entry.category == category)
    if event_type:
        query = query.where(Entry.event_type == event_type)

    query = query.order_by(Entry.occurred_at.desc()).limit(1)
    result = await session.execute(query)
    return result.scalar_one_or_none()


def format_time_ago(dt: datetime | None) -> str | None:
    """Format a datetime as 'Xh Ym ago' string."""
    if dt is None:
        return None

    now = datetime.now(UTC).replace(tzinfo=None)
    delta = now - dt

    total_minutes = int(delta.total_seconds() / 60)
    if total_minutes < 0:
        return "just now"

    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours == 0:
        return f"{minutes}m ago"
    elif minutes == 0:
        return f"{hours}h ago"
    else:
        return f"{hours}h {minutes}m ago"


async def get_daily_counts_for_chart(
    session: AsyncSession,
    days: int = 7,
) -> dict[str, list[dict[str, int | str]]]:
    """Get daily counts for meals, pees, and poops for the chart."""
    tz = ZoneInfo(settings.timezone)
    today = datetime.now(tz).date()

    # Build date range
    dates = [(today - timedelta(days=i)) for i in range(days - 1, -1, -1)]

    meals: list[dict[str, int | str]] = []
    pees: list[dict[str, int | str]] = []
    poops: list[dict[str, int | str]] = []

    for d in dates:
        # Get counts for this date
        start_local = datetime(d.year, d.month, d.day, tzinfo=tz)
        end_local = datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=tz)
        start_utc = start_local.astimezone(UTC).replace(tzinfo=None)
        end_utc = end_local.astimezone(UTC).replace(tzinfo=None)

        result = await session.execute(
            select(Entry.event_type, func.count(Entry.id))
            .where(
                and_(
                    Entry.occurred_at >= start_utc,
                    Entry.occurred_at <= end_utc,
                    Entry.deleted_at.is_(None),
                    Entry.event_type.in_(["meal", "pee", "poop"]),
                )
            )
            .group_by(Entry.event_type)
        )

        counts = {event_type: count for event_type, count in result.all()}
        label = d.strftime("%a")  # Mon, Tue, etc.

        meals.append({"date": label, "count": counts.get("meal", 0)})
        pees.append({"date": label, "count": counts.get("pee", 0)})
        poops.append({"date": label, "count": counts.get("poop", 0)})

    return {
        "meals": meals,
        "pees": pees,
        "poops": poops,
    }


async def get_summary_data(
    session: AsyncSession,
    target_date: date | None = None,
) -> dict:
    """Get all summary data for the summary page/API."""
    tz = ZoneInfo(settings.timezone)
    if target_date is None:
        target_date = datetime.now(tz).date()

    # Get counts
    category_counts = await get_category_counts(session, target_date)
    event_counts = await get_event_counts(session, target_date)

    # Get last events
    last_meal = await get_last_event(session, event_type="meal")
    last_pee = await get_last_event(session, event_type="pee")
    last_poop = await get_last_event(session, event_type="poop")

    # Get chart data
    chart_data = await get_daily_counts_for_chart(session)

    return {
        "date": target_date.isoformat(),
        "category_counts": category_counts,
        "event_counts": event_counts,
        "last_meal": {
            "occurred_at": last_meal.occurred_at.isoformat() if last_meal else None,
            "ago": format_time_ago(last_meal.occurred_at) if last_meal else None,
        },
        "last_pee": {
            "occurred_at": last_pee.occurred_at.isoformat() if last_pee else None,
            "ago": format_time_ago(last_pee.occurred_at) if last_pee else None,
        },
        "last_poop": {
            "occurred_at": last_poop.occurred_at.isoformat() if last_poop else None,
            "ago": format_time_ago(last_poop.occurred_at) if last_poop else None,
        },
        "chart": chart_data,
    }
