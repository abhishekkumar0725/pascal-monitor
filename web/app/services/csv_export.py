from __future__ import annotations

import csv
import io
import os
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import settings
from app.models import Entry

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


async def get_entries_for_export(
    session: AsyncSession,
    category: str | None = None,
) -> Sequence[Entry]:
    """Get all non-deleted entries, optionally filtered by category."""
    query = select(Entry).where(Entry.deleted_at.is_(None)).order_by(Entry.occurred_at)
    if category:
        query = query.where(Entry.category == category)
    result = await session.execute(query)
    return result.scalars().all()


def format_timestamp(dt, tz: ZoneInfo) -> str:
    """Format a datetime for CSV export in local timezone."""
    local_dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def atomic_write(path: Path, content: str) -> None:
    """Write content to file atomically using tmp file + os.replace().

    Ensures partial files never appear even on crash.
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Clean up tmp file if something goes wrong before replace
        if tmp_path.exists():
            tmp_path.unlink()
        raise


async def export_feeding_csv(session: AsyncSession) -> str:
    """Export feeding entries in legacy CSV format: timestamp,event_type,amount,notes"""
    tz = ZoneInfo(settings.timezone)
    entries = await get_entries_for_export(session, category="feeding")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "event_type", "amount", "notes"])

    for entry in entries:
        writer.writerow([
            format_timestamp(entry.occurred_at, tz),
            entry.event_type,
            entry.amount or "",
            entry.notes or "",
        ])

    return output.getvalue()


async def export_bathroom_csv(session: AsyncSession) -> str:
    """Export bathroom entries in legacy CSV format: timestamp,event_type,location,notes"""
    tz = ZoneInfo(settings.timezone)
    entries = await get_entries_for_export(session, category="bathroom")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "event_type", "location", "notes"])

    for entry in entries:
        writer.writerow([
            format_timestamp(entry.occurred_at, tz),
            entry.event_type,
            entry.location or "",
            entry.notes or "",
        ])

    return output.getvalue()


async def export_sleep_csv(session: AsyncSession) -> str:
    """Export sleep entries in legacy CSV format: timestamp,event_type,notes"""
    tz = ZoneInfo(settings.timezone)
    entries = await get_entries_for_export(session, category="sleep")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "event_type", "notes"])

    for entry in entries:
        writer.writerow([
            format_timestamp(entry.occurred_at, tz),
            entry.event_type,
            entry.notes or "",
        ])

    return output.getvalue()


async def export_training_csv(session: AsyncSession) -> str:
    """Export training entries in legacy CSV format: timestamp,command,result,notes"""
    tz = ZoneInfo(settings.timezone)
    entries = await get_entries_for_export(session, category="training")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "command", "result", "notes"])

    for entry in entries:
        writer.writerow([
            format_timestamp(entry.occurred_at, tz),
            entry.command or "",
            entry.result or "",
            entry.notes or "",
        ])

    return output.getvalue()


async def export_entries_full_csv(session: AsyncSession) -> str:
    """Export all entries with full schema including logged_by and category."""
    tz = ZoneInfo(settings.timezone)
    entries = await get_entries_for_export(session)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "category",
        "event_type",
        "timestamp",
        "logged_at",
        "logged_by",
        "amount",
        "location",
        "command",
        "result",
        "duration_min",
        "distance_km",
        "cost_usd",
        "notes",
        "updated_at",
    ])

    for entry in entries:
        writer.writerow([
            entry.id,
            entry.category,
            entry.event_type,
            format_timestamp(entry.occurred_at, tz),
            format_timestamp(entry.logged_at, tz),
            entry.logged_by,
            entry.amount or "",
            entry.location or "",
            entry.command or "",
            entry.result or "",
            entry.duration_min if entry.duration_min is not None else "",
            entry.distance_km if entry.distance_km is not None else "",
            entry.cost_usd if entry.cost_usd is not None else "",
            entry.notes or "",
            format_timestamp(entry.updated_at, tz),
        ])

    return output.getvalue()


async def export_all_zip(session: AsyncSession) -> bytes:
    """Export all four legacy CSVs as a zip file."""
    feeding = await export_feeding_csv(session)
    bathroom = await export_bathroom_csv(session)
    sleep = await export_sleep_csv(session)
    training = await export_training_csv(session)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("feeding.csv", feeding)
        zf.writestr("bathroom.csv", bathroom)
        zf.writestr("sleep.csv", sleep)
        zf.writestr("training.csv", training)

    return buffer.getvalue()


async def write_all_csvs_to_dir(session: AsyncSession, output_dir: Path) -> dict[str, Path]:
    """Write all four legacy CSVs to a directory atomically.

    Returns a dict mapping filename to the written path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {}

    feeding_content = await export_feeding_csv(session)
    feeding_path = output_dir / "feeding.csv"
    atomic_write(feeding_path, feeding_content)
    files["feeding.csv"] = feeding_path

    bathroom_content = await export_bathroom_csv(session)
    bathroom_path = output_dir / "bathroom.csv"
    atomic_write(bathroom_path, bathroom_content)
    files["bathroom.csv"] = bathroom_path

    sleep_content = await export_sleep_csv(session)
    sleep_path = output_dir / "sleep.csv"
    atomic_write(sleep_path, sleep_content)
    files["sleep.csv"] = sleep_path

    training_content = await export_training_csv(session)
    training_path = output_dir / "training.csv"
    atomic_write(training_path, training_content)
    files["training.csv"] = training_path

    return files
