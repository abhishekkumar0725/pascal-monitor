from __future__ import annotations

import csv
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry
from app.scripts.import_existing_csvs import (
    load_bathroom_csv,
    load_feeding_csv,
    load_sleep_csv,
    load_training_csv,
    parse_timestamp,
)


def test_parse_timestamp_converts_to_utc() -> None:
    """Test timestamp parsing converts local time to UTC."""
    with patch("app.scripts.import_existing_csvs.LOCAL_TZ", ZoneInfo("America/New_York")):
        result = parse_timestamp("2026-04-15 12:00:00")
        assert result.hour == 16


def test_load_feeding_csv() -> None:
    """Test loading feeding.csv data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "event_type", "amount", "notes"])
        writer.writerow(["2026-04-15 12:00:00", "meal", "0.5 cup", "lunch"])
        writer.writerow(["2026-04-15 18:00:00", "water", "", ""])
        f.flush()

        entries = load_feeding_csv(Path(f.name))
        assert len(entries) == 2
        assert entries[0]["category"] == "feeding"
        assert entries[0]["event_type"] == "meal"
        assert entries[0]["amount"] == "0.5 cup"
        assert entries[0]["notes"] == "lunch"
        assert entries[1]["amount"] is None
        assert entries[1]["notes"] is None


def test_load_bathroom_csv() -> None:
    """Test loading bathroom.csv data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "event_type", "location", "notes"])
        writer.writerow(["2026-04-15 12:00:00", "pee", "outside", "good boy"])
        f.flush()

        entries = load_bathroom_csv(Path(f.name))
        assert len(entries) == 1
        assert entries[0]["category"] == "bathroom"
        assert entries[0]["event_type"] == "pee"
        assert entries[0]["location"] == "outside"


def test_load_sleep_csv() -> None:
    """Test loading sleep.csv data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "event_type", "notes"])
        writer.writerow(["2026-04-15 22:00:00", "sleep", "bedtime"])
        writer.writerow(["2026-04-16 07:00:00", "wake", ""])
        f.flush()

        entries = load_sleep_csv(Path(f.name))
        assert len(entries) == 2
        assert entries[0]["category"] == "sleep"
        assert entries[1]["event_type"] == "wake"


def test_load_training_csv() -> None:
    """Test loading training.csv data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "command", "result", "notes"])
        writer.writerow(["2026-04-15 10:00:00", "sit", "pass", "good session"])
        f.flush()

        entries = load_training_csv(Path(f.name))
        assert len(entries) == 1
        assert entries[0]["category"] == "training"
        assert entries[0]["event_type"] == "training"
        assert entries[0]["command"] == "sit"
        assert entries[0]["result"] == "pass"


@pytest.mark.asyncio
async def test_entry_model_insert(test_session: AsyncSession) -> None:
    """Test that Entry model can be inserted into the database."""
    entry = Entry(
        category="feeding",
        event_type="meal",
        occurred_at=datetime.utcnow(),
        logged_by="test",
    )
    test_session.add(entry)
    await test_session.commit()

    result = await test_session.execute(select(func.count()).select_from(Entry))
    count = result.scalar()
    assert count == 1
