from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models import Entry


@pytest.mark.asyncio
async def test_home_page_returns_200(client: AsyncClient) -> None:
    """Test that the home page loads successfully."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "Pascal" in response.text
    assert "Pee" in response.text
    assert "Poop" in response.text
    assert "Meal" in response.text
    assert "Water" in response.text
    assert "Sleep" in response.text
    assert "Wake" in response.text


@pytest.mark.asyncio
async def test_log_pee_creates_entry(client: AsyncClient, test_session) -> None:
    """Test that POST /log creates a bathroom entry."""
    response = await client.post(
        "/log",
        data={"category": "bathroom", "event_type": "pee"},
    )
    assert response.status_code == 200
    assert "Pee logged" in response.text

    # Verify entry was created in DB
    result = await test_session.execute(
        select(Entry).where(Entry.category == "bathroom", Entry.event_type == "pee")
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.logged_by == "Abhishek"  # Default user


@pytest.mark.asyncio
async def test_log_meal_creates_entry(client: AsyncClient, test_session) -> None:
    """Test that POST /log creates a feeding entry."""
    response = await client.post(
        "/log",
        data={"category": "feeding", "event_type": "meal"},
    )
    assert response.status_code == 200
    assert "Meal logged" in response.text

    result = await test_session.execute(
        select(Entry).where(Entry.category == "feeding", Entry.event_type == "meal")
    )
    entry = result.scalar_one_or_none()
    assert entry is not None


@pytest.mark.asyncio
async def test_log_sleep_creates_entry(client: AsyncClient, test_session) -> None:
    """Test that POST /log creates a sleep entry."""
    response = await client.post(
        "/log",
        data={"category": "sleep", "event_type": "sleep"},
    )
    assert response.status_code == 200
    assert "Sleep logged" in response.text


@pytest.mark.asyncio
async def test_log_with_cookie_uses_user(client: AsyncClient, test_session) -> None:
    """Test that POST /log respects the logged_by cookie."""
    client.cookies.set("logged_by", "Partner")
    response = await client.post(
        "/log",
        data={"category": "bathroom", "event_type": "poop"},
    )
    assert response.status_code == 200

    result = await test_session.execute(select(Entry).where(Entry.event_type == "poop"))
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.logged_by == "Partner"


@pytest.mark.asyncio
async def test_set_user_sets_cookie(client: AsyncClient) -> None:
    """Test that POST /set-user sets the logged_by cookie."""
    response = await client.post(
        "/set-user",
        data={"logged_by": "Walker"},
    )
    assert response.status_code == 200
    assert "logged_by" in response.cookies


@pytest.mark.asyncio
async def test_multiple_logs_create_multiple_entries(client: AsyncClient, test_session) -> None:
    """Test that multiple POST /log calls create multiple entries."""
    await client.post("/log", data={"category": "bathroom", "event_type": "pee"})
    await client.post("/log", data={"category": "bathroom", "event_type": "pee"})
    await client.post("/log", data={"category": "feeding", "event_type": "water"})

    result = await test_session.execute(select(func.count()).select_from(Entry))
    count = result.scalar()
    assert count == 3
