import pytest
from httpx import AsyncClient

from app.schemas.interaction import CheckRequest


# ──────────────── Unit-тесты схем ────────────────

def test_check_request_min_drugs():
    with pytest.raises(Exception):
        CheckRequest(drugs=["Аспирин"])


def test_check_request_max_drugs():
    with pytest.raises(Exception):
        CheckRequest(drugs=[f"Drug{i}" for i in range(21)])


def test_check_request_valid():
    req = CheckRequest(drugs=["  Аспирин  ", "Варфарин"])
    assert req.drugs == ["Аспирин", "Варфарин"]  # trim whitespace


# ──────────────── Интеграционные тесты API ────────────────

async def _auth(client: AsyncClient) -> str:
    import uuid
    email = f"inter_{uuid.uuid4().hex[:6]}@test.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "pass123"})
    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": "pass123"})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_submit_check_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/interactions/check", json={"drugs": ["Аспирин", "Варфарин"]})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_submit_check_too_few_drugs(client: AsyncClient):
    token = await _auth(client)
    resp = await client.post(
        "/api/v1/interactions/check",
        json={"drugs": ["Аспирин"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_check_accepted(client: AsyncClient):
    token = await _auth(client)
    resp = await client.post(
        "/api/v1/interactions/check",
        json={"drugs": ["Варфарин", "Ибупрофен"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    # 402 если нет баланса, 202 если есть
    assert resp.status_code in (202, 402)


@pytest.mark.asyncio
async def test_get_check_not_found(client: AsyncClient):
    token = await _auth(client)
    resp = await client.get("/api/v1/interactions/check/99999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_history_empty(client: AsyncClient):
    token = await _auth(client)
    resp = await client.get("/api/v1/interactions/history", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
