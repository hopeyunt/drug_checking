import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.core.security import hash_password


# ── Вспомогательные функции ───────────────────────────────────────────────────

async def _create_admin(db: AsyncSession) -> tuple[str, str]:
    """Создаёт admin-пользователя напрямую в БД и возвращает (email, password)."""
    email = f"admin_{uuid.uuid4().hex[:6]}@test.com"
    password = "admin_pass123"
    user = User(
        email=email,
        hashed_password=hash_password(password),
        is_admin=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return email, password


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return resp.json()["access_token"]


async def _register_login(client: AsyncClient) -> str:
    email = f"user_{uuid.uuid4().hex[:6]}@test.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "pass123"})
    return await _login(client, email, "pass123")


# ── /admin/stats ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_stats_forbidden_for_regular_user(client: AsyncClient):
    token = await _register_login(client)
    resp = await client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_unauthorized(client: AsyncClient):
    resp = await client.get("/api/v1/admin/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_stats_ok(client: AsyncClient, db: AsyncSession):
    email, password = await _create_admin(db)
    token = await _login(client, email, password)
    resp = await client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_checks" in data
    assert "completed_checks" in data
    assert "total_revenue_credits" in data
    assert "loyalty_distribution" in data
    assert data["total_users"] >= 1


# ── /admin/users ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_users_list(client: AsyncClient, db: AsyncSession):
    email, password = await _create_admin(db)
    token = await _login(client, email, password)
    resp = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert len(users) >= 1
    assert any(u["email"] == email for u in users)


@pytest.mark.asyncio
async def test_admin_users_pagination(client: AsyncClient, db: AsyncSession):
    email, password = await _create_admin(db)
    token = await _login(client, email, password)
    resp = await client.get(
        "/api/v1/admin/users?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) <= 2


# ── /admin/loyalty ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_loyalty_list(client: AsyncClient, db: AsyncSession):
    email, password = await _create_admin(db)
    token = await _login(client, email, password)
    resp = await client.get("/api/v1/admin/loyalty", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    configs = resp.json()
    assert isinstance(configs, list)
    levels = {c["level"] for c in configs}
    assert {"bronze", "silver", "gold"} == levels


@pytest.mark.asyncio
async def test_admin_loyalty_update_silver(client: AsyncClient, db: AsyncSession):
    email, password = await _create_admin(db)
    token = await _login(client, email, password)

    resp = await client.patch(
        "/api/v1/admin/loyalty/silver",
        json={"min_predictions": 60, "discount_percent": "7"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == "silver"
    assert data["min_predictions"] == 60

    # Восстановим исходное значение
    await client.patch(
        "/api/v1/admin/loyalty/silver",
        json={"min_predictions": 50, "discount_percent": "5"},
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_admin_loyalty_update_not_found(client: AsyncClient, db: AsyncSession):
    email, password = await _create_admin(db)
    token = await _login(client, email, password)
    resp = await client.patch(
        "/api/v1/admin/loyalty/platinum",
        json={"min_predictions": 500, "discount_percent": "20"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
