import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
    assert "db" in data
    assert "redis" in data


@pytest.mark.asyncio
async def test_health_db_up(client: AsyncClient):
    resp = await client.get("/health")
    data = resp.json()
    assert data["db"] is True
