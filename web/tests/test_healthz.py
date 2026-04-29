from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz_returns_ok(client: AsyncClient) -> None:
    """Test that /healthz returns 200 with status ok."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data


@pytest.mark.asyncio
async def test_healthz_database_check(client: AsyncClient) -> None:
    """Test that /healthz checks database connectivity."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "ok"
