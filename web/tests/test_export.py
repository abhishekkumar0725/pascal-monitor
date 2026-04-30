from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry
from app.services.csv_export import atomic_write


async def create_test_entry(
    session: AsyncSession,
    category: str = "feeding",
    event_type: str = "meal",
    logged_by: str = "Test",
    **kwargs,
) -> Entry:
    """Helper to create a test entry."""
    now = datetime.now(UTC).replace(tzinfo=None)
    entry = Entry(
        category=category,
        event_type=event_type,
        occurred_at=now,
        logged_at=now,
        logged_by=logged_by,
        updated_at=now,
        **kwargs,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


# --- Export endpoint tests ---


@pytest.mark.asyncio
async def test_export_feeding_csv_headers(client: AsyncClient) -> None:
    """Test that /export/feeding.csv has correct headers."""
    response = await client.get("/export/feeding.csv")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]

    first_line = response.text.split("\n")[0].strip()
    assert first_line == "timestamp,event_type,amount,notes"


@pytest.mark.asyncio
async def test_export_bathroom_csv_headers(client: AsyncClient) -> None:
    """Test that /export/bathroom.csv has correct headers."""
    response = await client.get("/export/bathroom.csv")
    assert response.status_code == 200

    first_line = response.text.split("\n")[0].strip()
    assert first_line == "timestamp,event_type,location,notes"


@pytest.mark.asyncio
async def test_export_sleep_csv_headers(client: AsyncClient) -> None:
    """Test that /export/sleep.csv has correct headers."""
    response = await client.get("/export/sleep.csv")
    assert response.status_code == 200

    first_line = response.text.split("\n")[0].strip()
    assert first_line == "timestamp,event_type,notes"


@pytest.mark.asyncio
async def test_export_training_csv_headers(client: AsyncClient) -> None:
    """Test that /export/training.csv has correct headers."""
    response = await client.get("/export/training.csv")
    assert response.status_code == 200

    first_line = response.text.split("\n")[0].strip()
    assert first_line == "timestamp,command,result,notes"


@pytest.mark.asyncio
async def test_export_entries_full_csv_has_logged_by(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that entries_full.csv includes logged_by column."""
    await create_test_entry(test_session, logged_by="TestUser")
    await test_session.commit()

    response = await client.get("/export/entries_full.csv")
    assert response.status_code == 200

    first_line = response.text.split("\n")[0].strip()
    assert "logged_by" in first_line
    assert "category" in first_line


@pytest.mark.asyncio
async def test_export_excludes_soft_deleted(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that exports exclude soft-deleted entries."""
    entry = await create_test_entry(test_session, event_type="deleted_meal")
    entry.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await test_session.commit()

    response = await client.get("/export/feeding.csv")
    assert response.status_code == 200
    assert "deleted_meal" not in response.text


@pytest.mark.asyncio
async def test_export_all_zip(client: AsyncClient) -> None:
    """Test that /export/all.zip returns a valid zip with all 4 CSVs."""
    response = await client.get("/export/all.zip")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    # Verify it's a valid zip with the expected files
    zf = zipfile.ZipFile(BytesIO(response.content))
    names = zf.namelist()
    assert "feeding.csv" in names
    assert "bathroom.csv" in names
    assert "sleep.csv" in names
    assert "training.csv" in names


@pytest.mark.asyncio
async def test_legacy_csv_no_logged_by(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that legacy CSVs do NOT include logged_by column."""
    await create_test_entry(test_session, logged_by="SomeUser")
    await test_session.commit()

    for endpoint in ["/export/feeding.csv", "/export/bathroom.csv",
                     "/export/sleep.csv", "/export/training.csv"]:
        response = await client.get(endpoint)
        assert "logged_by" not in response.text.split("\n")[0].strip()


# --- Atomic write tests ---


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    """Test that atomic_write creates the target file."""
    target = tmp_path / "test.csv"
    atomic_write(target, "header1,header2\nvalue1,value2\n")

    assert target.exists()
    assert target.read_text() == "header1,header2\nvalue1,value2\n"


def test_atomic_write_no_tmp_file_left(tmp_path: Path) -> None:
    """Test that atomic_write doesn't leave .tmp files."""
    target = tmp_path / "test.csv"
    atomic_write(target, "content")

    tmp_file = tmp_path / "test.csv.tmp"
    assert not tmp_file.exists()


def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    """Test that atomic_write overwrites existing file."""
    target = tmp_path / "test.csv"
    target.write_text("old content")

    atomic_write(target, "new content")

    assert target.read_text() == "new content"


def test_atomic_write_failure_preserves_original(tmp_path: Path) -> None:
    """Test that if os.replace fails, original file is untouched."""
    target = tmp_path / "test.csv"
    target.write_text("original content")

    # Patch os.replace to raise an exception
    with patch("app.services.csv_export.os.replace") as mock_replace:
        mock_replace.side_effect = OSError("Simulated failure")

        with pytest.raises(OSError, match="Simulated failure"):
            atomic_write(target, "new content")

    # Original file should be untouched
    assert target.read_text() == "original content"

    # Tmp file should be cleaned up
    tmp_file = tmp_path / "test.csv.tmp"
    assert not tmp_file.exists()
