from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry


async def create_entry_direct(
    session: AsyncSession,
    category: str,
    event_type: str,
    **kwargs,
) -> Entry:
    """Helper to create an entry directly in the database."""
    now = datetime.now(UTC).replace(tzinfo=None)
    entry = Entry(
        category=category,
        event_type=event_type,
        occurred_at=kwargs.pop("occurred_at", now),
        logged_at=now,
        logged_by=kwargs.pop("logged_by", "Test"),
        updated_at=now,
        **kwargs,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


# --- Summary page tests ---


@pytest.mark.asyncio
async def test_summary_page_renders(client: AsyncClient) -> None:
    """Test that /summary page renders."""
    response = await client.get("/summary")
    assert response.status_code == 200
    assert "Summary" in response.text


@pytest.mark.asyncio
async def test_summary_page_shows_stats(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that summary page shows stat cards."""
    await create_entry_direct(test_session, "feeding", "meal")
    await create_entry_direct(test_session, "bathroom", "pee")
    await test_session.commit()

    response = await client.get("/summary")
    assert response.status_code == 200
    assert "Meals" in response.text
    assert "Pees" in response.text


@pytest.mark.asyncio
async def test_summary_page_has_chart(client: AsyncClient) -> None:
    """Test that summary page includes Chart.js chart."""
    response = await client.get("/summary")
    assert response.status_code == 200
    assert "chart.js" in response.text.lower()
    assert "weeklyChart" in response.text


# --- API endpoint tests ---


@pytest.mark.asyncio
async def test_api_summary_json_returns_json(client: AsyncClient) -> None:
    """Test that /api/summary.json returns valid JSON."""
    response = await client.get("/api/summary.json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    data = response.json()
    assert "date" in data
    assert "category_counts" in data
    assert "event_counts" in data
    assert "last_meal" in data
    assert "last_pee" in data
    assert "chart" in data


@pytest.mark.asyncio
async def test_api_summary_json_counts(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that /api/summary.json returns correct counts."""
    # Create some entries
    await create_entry_direct(test_session, "feeding", "meal")
    await create_entry_direct(test_session, "feeding", "meal")
    await create_entry_direct(test_session, "bathroom", "pee")
    await create_entry_direct(test_session, "bathroom", "poop")
    await test_session.commit()

    response = await client.get("/api/summary.json")
    data = response.json()

    assert data["event_counts"].get("meal", 0) == 2
    assert data["event_counts"].get("pee", 0) == 1
    assert data["event_counts"].get("poop", 0) == 1
    assert data["category_counts"].get("feeding", 0) == 2
    assert data["category_counts"].get("bathroom", 0) == 2


@pytest.mark.asyncio
async def test_api_summary_json_last_events(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that /api/summary.json returns last event times."""
    await create_entry_direct(test_session, "feeding", "meal")
    await create_entry_direct(test_session, "bathroom", "pee")
    await test_session.commit()

    response = await client.get("/api/summary.json")
    data = response.json()

    assert data["last_meal"]["occurred_at"] is not None
    assert data["last_meal"]["ago"] is not None
    assert data["last_pee"]["occurred_at"] is not None
    assert data["last_pee"]["ago"] is not None


@pytest.mark.asyncio
async def test_api_summary_json_chart_data(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that /api/summary.json returns chart data."""
    await create_entry_direct(test_session, "feeding", "meal")
    await test_session.commit()

    response = await client.get("/api/summary.json")
    data = response.json()

    assert "meals" in data["chart"]
    assert "pees" in data["chart"]
    assert "poops" in data["chart"]
    # Should have 7 days of data
    assert len(data["chart"]["meals"]) == 7


@pytest.mark.asyncio
async def test_api_summary_json_with_date_param(client: AsyncClient) -> None:
    """Test that /api/summary.json accepts date parameter."""
    response = await client.get("/api/summary.json?date=2024-01-15")
    assert response.status_code == 200

    data = response.json()
    assert data["date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_summary_excludes_deleted_entries(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that summary excludes soft-deleted entries."""
    entry = await create_entry_direct(test_session, "feeding", "meal")
    entry.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await test_session.commit()

    response = await client.get("/api/summary.json")
    data = response.json()

    # Deleted entry should not be counted
    assert data["event_counts"].get("meal", 0) == 0
