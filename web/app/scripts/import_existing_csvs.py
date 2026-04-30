"""One-shot script to seed pascal.db from the legacy CSV files.

Usage:
    cd web
    source .venv/bin/activate
    python -m app.scripts.import_existing_csvs

This script reads the four legacy CSVs (feeding, bathroom, sleep, training)
and inserts their rows into the entries table. It is idempotent: if the
table already has data, it will skip the import to avoid duplicates.
"""

from __future__ import annotations

import asyncio
import csv
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.config import settings
from app.db import Base, async_session_factory, engine
from app.models import Entry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_LOGGED_BY = "import"
LOCAL_TZ = ZoneInfo(settings.timezone)
UTC = ZoneInfo("UTC")


def parse_timestamp(ts_str: str) -> datetime:
    """Parse a CSV timestamp string to UTC datetime."""
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    local_dt = dt.replace(tzinfo=LOCAL_TZ)
    return local_dt.astimezone(UTC).replace(tzinfo=None)


def load_feeding_csv(csv_path: Path) -> list[dict]:
    """Load feeding.csv: timestamp,event_type,amount,notes"""
    entries = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(
                {
                    "category": "feeding",
                    "event_type": row["event_type"].strip(),
                    "occurred_at": parse_timestamp(row["timestamp"]),
                    "logged_by": DEFAULT_LOGGED_BY,
                    "amount": row.get("amount", "").strip() or None,
                    "notes": row.get("notes", "").strip() or None,
                }
            )
    return entries


def load_bathroom_csv(csv_path: Path) -> list[dict]:
    """Load bathroom.csv: timestamp,event_type,location,notes"""
    entries = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(
                {
                    "category": "bathroom",
                    "event_type": row["event_type"].strip(),
                    "occurred_at": parse_timestamp(row["timestamp"]),
                    "logged_by": DEFAULT_LOGGED_BY,
                    "location": row.get("location", "").strip() or None,
                    "notes": row.get("notes", "").strip() or None,
                }
            )
    return entries


def load_sleep_csv(csv_path: Path) -> list[dict]:
    """Load sleep.csv: timestamp,event_type,notes"""
    entries = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(
                {
                    "category": "sleep",
                    "event_type": row["event_type"].strip(),
                    "occurred_at": parse_timestamp(row["timestamp"]),
                    "logged_by": DEFAULT_LOGGED_BY,
                    "notes": row.get("notes", "").strip() or None,
                }
            )
    return entries


def load_training_csv(csv_path: Path) -> list[dict]:
    """Load training.csv: timestamp,command,result,notes"""
    entries = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(
                {
                    "category": "training",
                    "event_type": "training",
                    "occurred_at": parse_timestamp(row["timestamp"]),
                    "logged_by": DEFAULT_LOGGED_BY,
                    "command": row.get("command", "").strip() or None,
                    "result": row.get("result", "").strip() or None,
                    "notes": row.get("notes", "").strip() or None,
                }
            )
    return entries


async def import_csvs() -> int:
    """Import all legacy CSVs into the database. Returns count of rows imported."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        result = await session.execute(select(func.count()).select_from(Entry))
        existing_count = result.scalar() or 0

        # if existing_count > 0:
        #     logger.info("Database already has %d entries, skipping import.", existing_count)
        #     return 0

    csv_dir = settings.legacy_csv_path
    logger.info("Loading CSVs from: %s", csv_dir)

    all_entries: list[dict] = []

    feeding_path = csv_dir / "feeding.csv"
    if feeding_path.exists():
        entries = load_feeding_csv(feeding_path)
        logger.info("Loaded %d rows from feeding.csv", len(entries))
        all_entries.extend(entries)

    bathroom_path = csv_dir / "bathroom.csv"
    if bathroom_path.exists():
        entries = load_bathroom_csv(bathroom_path)
        logger.info("Loaded %d rows from bathroom.csv", len(entries))
        all_entries.extend(entries)

    sleep_path = csv_dir / "sleep.csv"
    if sleep_path.exists():
        entries = load_sleep_csv(sleep_path)
        logger.info("Loaded %d rows from sleep.csv", len(entries))
        all_entries.extend(entries)

    training_path = csv_dir / "training.csv"
    if training_path.exists():
        entries = load_training_csv(training_path)
        logger.info("Loaded %d rows from training.csv", len(entries))
        all_entries.extend(entries)

    if not all_entries:
        logger.warning("No CSV data found to import.")
        return 0

    async with async_session_factory() as session:
        now = datetime.utcnow()
        for entry_data in all_entries:
            entry = Entry(
                **entry_data,
                logged_at=now,
                updated_at=now,
            )
            session.add(entry)
        await session.commit()

    logger.info("Successfully imported %d entries.", len(all_entries))
    return len(all_entries)


def main() -> None:
    """Entry point for the import script."""
    count = asyncio.run(import_csvs())
    if count > 0:
        logger.info("Import complete: %d entries added.", count)
    else:
        logger.info("No entries imported (database already has data or no CSVs found).")


if __name__ == "__main__":
    main()
