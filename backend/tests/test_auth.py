import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, user_payload: dict):
    resp = await client.post("/api/v1/auth/register", json=user_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == user_payload["email"]
    assert data["balance"] == "50.00"  # welcome bonus
    assert data["loyalty_level"] == "bronze"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, user_payload: dict):
    await client.post("/api/v1/auth/register", json=user_payload)
    resp = await client.post("/api/v1/auth/register", json=user_payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, user_payload: dict):
    await client.post("/api/v1/auth/register", json=user_payload)
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": user_payload["email"], "password": user_payload["password"]},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, user_payload: dict):
    await client.post("/api/v1/auth/register", json=user_payload)
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": user_payload["email"], "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_unauthorized(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_authorized(client: AsyncClient, user_payload: dict):
    await client.post("/api/v1/auth/register", json=user_payload)
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": user_payload["email"], "password": user_payload["password"]},
    )
    token = login.json()["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == user_payload["email"]
