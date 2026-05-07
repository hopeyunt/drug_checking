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


@pytest.mark.asyncio
async def test_payment_stub_credits_user(client: AsyncClient):
    """Stub-эндпоинт должен начислить кредиты и вернуть 200."""
    import uuid
    token = await _register_and_login(client, f"stub_{uuid.uuid4().hex[:6]}@test.com")

    # Создаём платёж в тестовом режиме
    create_resp = await client.post(
        "/api/v1/billing/payment/create",
        json={"amount_rub": 199},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 200
    data = create_resp.json()
    confirmation_url = data["confirmation_url"]

    # Вызываем stub (подтверждение тестовой оплаты)
    stub_resp = await client.get(confirmation_url)
    assert stub_resp.status_code == 200
    stub_data = stub_resp.json()
    assert stub_data["credits"] == 50.0

    # Повторный вызов — кредиты не дублируются
    stub_resp2 = await client.get(confirmation_url)
    assert stub_resp2.status_code == 200
    assert "уже начислены" in stub_resp2.json()["message"]


@pytest.mark.asyncio
async def test_payment_stub_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/billing/payment/stub?id=nonexistent_id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_payment_history(client: AsyncClient):
    import uuid
    token = await _register_and_login(client, f"hist2_{uuid.uuid4().hex[:6]}@test.com")
    # Создаём платёж
    await client.post(
        "/api/v1/billing/payment/create",
        json={"amount_rub": 1490},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get("/api/v1/billing/payments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    payments = resp.json()
    assert len(payments) >= 1
    assert payments[0]["amount_rub"] == "1490.00" or float(payments[0]["amount_rub"]) == 1490


# ─── Unit-тесты yookassa_service ──────────────────────────────────────────────

def test_parse_webhook_success():
    import json
    from app.services.yookassa_service import parse_webhook

    body = json.dumps({
        "event": "payment.succeeded",
        "object": {
            "id": "pay_123",
            "status": "succeeded",
            "metadata": {"user_id": "42", "credits": "150"},
        },
    }).encode()

    result = parse_webhook(body)
    assert result is not None
    assert result["event"] == "payment.succeeded"
    assert result["yookassa_id"] == "pay_123"
    assert result["user_id"] == 42
    assert result["credits"] == 150


def test_parse_webhook_wrong_event():
    import json
    from app.services.yookassa_service import parse_webhook

    body = json.dumps({"event": "payment.canceled", "object": {}}).encode()
    assert parse_webhook(body) is None


def test_parse_webhook_invalid_json():
    from app.services.yookassa_service import parse_webhook
    assert parse_webhook(b"not json") is None


def test_parse_webhook_missing_metadata():
    import json
    from app.services.yookassa_service import parse_webhook

    body = json.dumps({
        "event": "payment.succeeded",
        "object": {"id": "pay_x", "status": "succeeded", "metadata": {}},
    }).encode()
    assert parse_webhook(body) is None


def test_verify_webhook_no_keys():
    from app.services.yookassa_service import verify_webhook_signature
    # В тестовом режиме (без ключей) подпись всегда принимается
    assert verify_webhook_signature(b"body", "any_signature") is True
