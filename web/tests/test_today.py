from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry


async def create_test_entry(
    session: AsyncSession,
    category: str = "bathroom",
    event_type: str = "pee",
    notes: str | None = None,
) -> Entry:
    """Helper to create a test entry."""
    now = datetime.now(UTC).replace(tzinfo=None)
    entry = Entry(
        category=category,
        event_type=event_type,
        occurred_at=now,
        logged_at=now,
        logged_by="Test",
        notes=notes,
        updated_at=now,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


@pytest.mark.asyncio
async def test_today_page_returns_200(client: AsyncClient) -> None:
    """Test that /today returns 200."""
    response = await client.get("/today")
    assert response.status_code == 200
    assert "Today's Log" in response.text


@pytest.mark.asyncio
async def test_today_shows_entries(client: AsyncClient, test_session: AsyncSession) -> None:
    """Test that /today shows today's entries."""
    await create_test_entry(test_session, event_type="pee")
    await test_session.commit()

    response = await client.get("/today")
    assert response.status_code == 200
    assert "pee" in response.text.lower()


@pytest.mark.asyncio
async def test_today_excludes_deleted_entries(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that /today excludes soft-deleted entries."""
    entry = await create_test_entry(test_session, event_type="deleted_test")
    entry.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await test_session.commit()

    response = await client.get("/today")
    assert response.status_code == 200
    assert "deleted_test" not in response.text


@pytest.mark.asyncio
async def test_today_with_date_param(client: AsyncClient) -> None:
    """Test that /today accepts a date parameter."""
    response = await client.get("/today?date=2026-04-15")
    assert response.status_code == 200
    assert "April 15, 2026" in response.text


@pytest.mark.asyncio
async def test_edit_form_returns_form(client: AsyncClient, test_session: AsyncSession) -> None:
    """Test that GET /entries/{id}/edit returns an edit form."""
    entry = await create_test_entry(test_session)
    await test_session.commit()

    response = await client.get(f"/entries/{entry.id}/edit")
    assert response.status_code == 200
    assert "form" in response.text.lower()
    assert entry.event_type in response.text


@pytest.mark.asyncio
async def test_edit_form_404_for_missing_entry(client: AsyncClient) -> None:
    """Test that GET /entries/{id}/edit returns 404 for missing entry."""
    response = await client.get("/entries/99999/edit")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_entry(client: AsyncClient, test_session: AsyncSession) -> None:
    """Test that POST /entries/{id} updates an entry."""
    entry = await create_test_entry(test_session)
    await test_session.commit()
    original_updated_at = entry.updated_at

    response = await client.post(
        f"/entries/{entry.id}",
        data={"event_type": "poop", "notes": "updated note"},
    )
    assert response.status_code == 200
    assert "poop" in response.text.lower()

    await test_session.refresh(entry)
    assert entry.event_type == "poop"
    assert entry.notes == "updated note"
    assert entry.updated_at > original_updated_at


@pytest.mark.asyncio
async def test_update_entry_with_new_notes(client: AsyncClient, test_session: AsyncSession) -> None:
    """Test that POST /entries/{id} can update notes field."""
    entry = await create_test_entry(test_session, notes="original note")
    await test_session.commit()

    response = await client.post(
        f"/entries/{entry.id}",
        data={"event_type": "pee", "notes": "new note"},
    )
    assert response.status_code == 200
    # Verify the response contains the new note
    assert "new note" in response.text


@pytest.mark.asyncio
async def test_delete_entry_soft_deletes(client: AsyncClient, test_session: AsyncSession) -> None:
    """Test that DELETE /entries/{id} soft-deletes an entry."""
    entry = await create_test_entry(test_session)
    await test_session.commit()
    assert entry.deleted_at is None

    response = await client.delete(f"/entries/{entry.id}")
    assert response.status_code == 200
    assert "Undo" in response.text

    await test_session.refresh(entry)
    assert entry.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_entry_404_for_missing(client: AsyncClient) -> None:
    """Test that DELETE /entries/{id} returns 404 for missing entry."""
    response = await client.delete("/entries/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_undelete_entry_restores(client: AsyncClient, test_session: AsyncSession) -> None:
    """Test that POST /entries/{id}/undelete restores a deleted entry."""
    entry = await create_test_entry(test_session)
    entry.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await test_session.commit()

    response = await client.post(f"/entries/{entry.id}/undelete")
    assert response.status_code == 200
    assert "restored" in response.text.lower()

    await test_session.refresh(entry)
    assert entry.deleted_at is None


@pytest.mark.asyncio
async def test_get_entry_row_returns_row(client: AsyncClient, test_session: AsyncSession) -> None:
    """Test that GET /entries/{id}/row returns an entry row fragment."""
    entry = await create_test_entry(test_session)
    await test_session.commit()

    response = await client.get(f"/entries/{entry.id}/row")
    assert response.status_code == 200
    assert entry.event_type in response.text
