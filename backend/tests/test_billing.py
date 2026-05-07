import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from httpx import AsyncClient

from app.services.billing_service import (
    _compute_discount, _compute_cost, _compute_loyalty_level
)
from app.core.config import settings


# ─── Вспомогательная функция: mock-конфиги без БД ────────────────────────────

def _make_configs(
    bronze_discount=Decimal("0"),
    silver_discount=Decimal("5"),
    gold_discount=Decimal("15"),
    silver_threshold=50,
    gold_threshold=200,
) -> dict:
    def cfg(level, min_pred, discount):
        c = MagicMock()
        c.level = level
        c.min_predictions = min_pred
        c.discount_percent = discount
        return c

    return {
        "bronze": cfg("bronze", 0,               bronze_discount),
        "silver": cfg("silver", silver_threshold, silver_discount),
        "gold":   cfg("gold",   gold_threshold,   gold_discount),
    }


# ─── Unit-тесты бизнес-логики ─────────────────────────────────────────────────

def test_discount_bronze():
    assert _compute_discount(_make_configs(), "bronze") == Decimal("0")


def test_discount_silver():
    assert _compute_discount(_make_configs(), "silver") == Decimal("5")


def test_discount_gold():
    assert _compute_discount(_make_configs(), "gold") == Decimal("15")


def test_discount_unknown_level():
    assert _compute_discount(_make_configs(), "platinum") == Decimal("0")


def test_cost_bronze():
    assert _compute_cost(_make_configs(), "bronze") == settings.CHECK_COST


def test_cost_silver():
    expected = settings.CHECK_COST * Decimal("0.95")
    assert _compute_cost(_make_configs(), "silver") == expected


def test_cost_gold():
    expected = settings.CHECK_COST * Decimal("0.85")
    assert _compute_cost(_make_configs(), "gold") == expected


def test_loyalty_recalculation_bronze():
    configs = _make_configs()
    assert _compute_loyalty_level(configs, 0) == "bronze"
    assert _compute_loyalty_level(configs, 49) == "bronze"


def test_loyalty_recalculation_silver():
    configs = _make_configs()
    assert _compute_loyalty_level(configs, 50) == "silver"
    assert _compute_loyalty_level(configs, 199) == "silver"


def test_loyalty_recalculation_gold():
    configs = _make_configs()
    assert _compute_loyalty_level(configs, 200) == "gold"
    assert _compute_loyalty_level(configs, 1000) == "gold"


def test_loyalty_custom_thresholds():
    configs = _make_configs(silver_threshold=10, gold_threshold=100)
    assert _compute_loyalty_level(configs, 9) == "bronze"
    assert _compute_loyalty_level(configs, 10) == "silver"
    assert _compute_loyalty_level(configs, 100) == "gold"


# ─── Интеграционные тесты API ─────────────────────────────────────────────────

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
    assert len(txs) >= 1
    assert txs[0]["type"] == "credit"


@pytest.mark.asyncio
async def test_payment_create_invalid_amount(client: AsyncClient):
    import uuid
    token = await _register_and_login(client, f"pay_{uuid.uuid4().hex[:6]}@test.com")
    resp = await client.post(
        "/api/v1/billing/payment/create",
        json={"amount_rub": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_payment_create_test_mode(client: AsyncClient):
    import uuid
    token = await _register_and_login(client, f"pay2_{uuid.uuid4().hex[:6]}@test.com")
    resp = await client.post(
        "/api/v1/billing/payment/create",
        json={"amount_rub": 499},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["test_mode"] is True
    assert data["credits"] == 150
    assert "confirmation_url" in data
