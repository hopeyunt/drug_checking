import pytest
from decimal import Decimal
from httpx import AsyncClient

from app.services.billing_service import (
    calculate_cost, get_discount_percent, recalculate_loyalty
)
from app.core.config import settings


# ──────────────── Unit-тесты бизнес-логики ────────────────

def test_discount_bronze():
    assert get_discount_percent("bronze") == Decimal("0")


def test_discount_silver():
    assert get_discount_percent("silver") == Decimal("5")


def test_discount_gold():
    assert get_discount_percent("gold") == Decimal("15")


def test_cost_bronze():
    expected = settings.CHECK_COST  # без скидки
    assert calculate_cost("bronze") == expected


def test_cost_silver():
    expected = settings.CHECK_COST * Decimal("0.95")
    assert calculate_cost("silver") == expected


def test_cost_gold():
    expected = settings.CHECK_COST * Decimal("0.85")
    assert calculate_cost("gold") == expected


def test_loyalty_recalculation_bronze():
    assert recalculate_loyalty(0) == "bronze"
    assert recalculate_loyalty(49) == "bronze"


def test_loyalty_recalculation_silver():
    assert recalculate_loyalty(50) == "silver"
    assert recalculate_loyalty(199) == "silver"


def test_loyalty_recalculation_gold():
    assert recalculate_loyalty(200) == "gold"
    assert recalculate_loyalty(1000) == "gold"


# ──────────────── Интеграционные тесты API ────────────────

async def _register_and_login(client: AsyncClient, email: str, password: str = "pass123") -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_balance_initial(client: AsyncClient):
    import uuid
    token = await _register_and_login(client, f"billing_{uuid.uuid4().hex[:6]}@test.com")
    resp = await client.get("/api/v1/billing/balance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["balance"]) == float(settings.WELCOME_BONUS)
    assert data["loyalty_level"] == "bronze"
    assert float(data["discount_percent"]) == 0.0


@pytest.mark.asyncio
async def test_topup(client: AsyncClient):
    import uuid
    token = await _register_and_login(client, f"topup_{uuid.uuid4().hex[:6]}@test.com")
    resp = await client.post(
        "/api/v1/billing/topup",
        json={"amount": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["balance"]) == float(settings.WELCOME_BONUS) + 100


@pytest.mark.asyncio
async def test_topup_negative_amount(client: AsyncClient):
    import uuid
    token = await _register_and_login(client, f"neg_{uuid.uuid4().hex[:6]}@test.com")
    resp = await client.post(
        "/api/v1/billing/topup",
        json={"amount": -50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_transactions_history(client: AsyncClient):
    import uuid
    token = await _register_and_login(client, f"hist_{uuid.uuid4().hex[:6]}@test.com")
    resp = await client.get("/api/v1/billing/transactions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    txs = resp.json()
    assert len(txs) >= 1  # минимум welcome bonus транзакция
    assert txs[0]["type"] == "credit"
