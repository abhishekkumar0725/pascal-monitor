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
        occurred_at=now,
        logged_at=now,
        logged_by=kwargs.pop("logged_by", "Test"),
        updated_at=now,
        **kwargs,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


# --- Form endpoint tests ---


@pytest.mark.asyncio
async def test_form_expand_returns_form(client: AsyncClient) -> None:
    """Test that /form/expand returns a form with category select."""
    response = await client.get("/form/expand")
    assert response.status_code == 200
    assert "form" in response.text.lower()
    assert 'name="category"' in response.text
    assert 'name="event_type"' in response.text


@pytest.mark.asyncio
async def test_form_collapse_returns_button(client: AsyncClient) -> None:
    """Test that /form/collapse returns the More options button."""
    response = await client.get("/form/collapse")
    assert response.status_code == 200
    assert "More options" in response.text


@pytest.mark.asyncio
async def test_form_event_types_feeding(client: AsyncClient) -> None:
    """Test that event types for feeding category are correct."""
    response = await client.get("/form/event-types?category=feeding")
    assert response.status_code == 200
    assert "meal" in response.text.lower()
    assert "water" in response.text.lower()
    assert "treat" in response.text.lower()


@pytest.mark.asyncio
async def test_form_event_types_walk(client: AsyncClient) -> None:
    """Test that event types for walk category are correct."""
    response = await client.get("/form/event-types?category=walk")
    assert response.status_code == 200
    assert "walk" in response.text.lower()


@pytest.mark.asyncio
async def test_form_category_fields_feeding(client: AsyncClient) -> None:
    """Test that category fields for feeding include amount."""
    response = await client.get("/form/category-fields?category=feeding")
    assert response.status_code == 200
    assert "amount" in response.text.lower()


@pytest.mark.asyncio
async def test_form_category_fields_walk(client: AsyncClient) -> None:
    """Test that category fields for walk include duration and distance."""
    response = await client.get("/form/category-fields?category=walk")
    assert response.status_code == 200
    assert "duration" in response.text.lower()
    assert "distance" in response.text.lower()


@pytest.mark.asyncio
async def test_form_category_fields_spending(client: AsyncClient) -> None:
    """Test that category fields for spending include cost."""
    response = await client.get("/form/category-fields?category=spending")
    assert response.status_code == 200
    assert "cost" in response.text.lower()


# --- Full log endpoint tests ---


@pytest.mark.asyncio
async def test_log_full_creates_entry(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that POST /log/full creates an entry."""
    response = await client.post(
        "/log/full",
        data={
            "category": "feeding",
            "event_type": "meal",
            "amount": "1 cup",
            "notes": "Test meal",
        },
    )
    assert response.status_code == 200
    assert "logged" in response.text.lower()


@pytest.mark.asyncio
async def test_log_full_walk_entry(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that POST /log/full can create a walk entry."""
    response = await client.post(
        "/log/full",
        data={
            "category": "walk",
            "event_type": "walk",
            "duration_min": "30",
            "distance_km": "1.5",
        },
    )
    assert response.status_code == 200
    assert "logged" in response.text.lower()


@pytest.mark.asyncio
async def test_log_full_spending_entry(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that POST /log/full can create a spending entry."""
    response = await client.post(
        "/log/full",
        data={
            "category": "spending",
            "event_type": "food",
            "cost_usd": "25.99",
        },
    )
    assert response.status_code == 200
    assert "logged" in response.text.lower()


# --- Today page rendering tests for new categories ---


@pytest.mark.asyncio
async def test_today_shows_walk_entry(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that walk entries appear on /today with duration and distance."""
    await create_entry_direct(
        test_session,
        category="walk",
        event_type="walk",
        duration_min=30,
        distance_km=1.5,
    )
    await test_session.commit()

    response = await client.get("/today")
    assert response.status_code == 200
    assert "walk" in response.text.lower()
    assert "30 min" in response.text


@pytest.mark.asyncio
async def test_today_shows_vet_entry(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that vet entries appear on /today."""
    await create_entry_direct(
        test_session,
        category="vet",
        event_type="checkup",
        notes="Annual checkup",
    )
    await test_session.commit()

    response = await client.get("/today")
    assert response.status_code == 200
    assert "vet" in response.text.lower()


@pytest.mark.asyncio
async def test_today_shows_spending_entry(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Test that spending entries appear on /today with cost."""
    await create_entry_direct(
        test_session,
        category="spending",
        event_type="food",
        cost_usd=25.99,
    )
    await test_session.commit()

    response = await client.get("/today")
    assert response.status_code == 200
    assert "spending" in response.text.lower()
    assert "$25.99" in response.text


@pytest.mark.asyncio
async def test_home_has_more_options_button(client: AsyncClient) -> None:
    """Test that home page has the More options button."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "More options" in response.text
