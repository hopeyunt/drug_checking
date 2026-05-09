"""
Юнит-тесты для чистых функций (без БД и Redis).
Покрывают: security, billing_service (pure), interaction_tasks (pure).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# ──────────────────────────────────────────────────────────
# security.py
# ──────────────────────────────────────────────────────────

from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    decode_token,
)


def test_hash_and_verify_password():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)


def test_verify_wrong_password():
    hashed = hash_password("correct")
    assert not verify_password("wrong", hashed)


def test_create_and_decode_token():
    token = create_access_token({"sub": "user@test.com", "user_id": 42})
    payload = decode_token(token)
    assert payload["sub"] == "user@test.com"
    assert payload["user_id"] == 42


def test_decode_invalid_token_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        decode_token("this.is.not.a.valid.token")
    assert exc_info.value.status_code == 401


def test_decode_tampered_token_raises():
    from fastapi import HTTPException
    token = create_access_token({"sub": "user@test.com"})
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(HTTPException):
        decode_token(tampered)


# ──────────────────────────────────────────────────────────
# billing_service.py — чистые вычислительные функции
# ──────────────────────────────────────────────────────────

from app.services.billing_service import (
    _compute_discount,
    _compute_cost,
    _compute_loyalty_level,
    _recalculate_from_defaults,
)


_MOCK_CONFIGS = {
    "bronze": {"min_predictions": 0,   "discount_percent": Decimal("0")},
    "silver": {"min_predictions": 50,  "discount_percent": Decimal("5")},
    "gold":   {"min_predictions": 200, "discount_percent": Decimal("15")},
}


def test_compute_discount_bronze():
    assert _compute_discount(_MOCK_CONFIGS, "bronze") == Decimal("0")


def test_compute_discount_silver():
    assert _compute_discount(_MOCK_CONFIGS, "silver") == Decimal("5")


def test_compute_discount_gold():
    assert _compute_discount(_MOCK_CONFIGS, "gold") == Decimal("15")


def test_compute_discount_unknown_level():
    assert _compute_discount(_MOCK_CONFIGS, "platinum") == Decimal("0")


def test_compute_cost_no_discount():
    from app.core.config import settings
    cost = _compute_cost(_MOCK_CONFIGS, "bronze")
    assert cost == settings.CHECK_COST


def test_compute_cost_with_discount():
    from app.core.config import settings
    cost = _compute_cost(_MOCK_CONFIGS, "gold")
    expected = settings.CHECK_COST * Decimal("0.85")
    assert cost == expected


def test_compute_loyalty_level_bronze():
    assert _compute_loyalty_level(_MOCK_CONFIGS, 0) == "bronze"
    assert _compute_loyalty_level(_MOCK_CONFIGS, 49) == "bronze"


def test_compute_loyalty_level_silver():
    assert _compute_loyalty_level(_MOCK_CONFIGS, 50) == "silver"
    assert _compute_loyalty_level(_MOCK_CONFIGS, 199) == "silver"


def test_compute_loyalty_level_gold():
    assert _compute_loyalty_level(_MOCK_CONFIGS, 200) == "gold"
    assert _compute_loyalty_level(_MOCK_CONFIGS, 9999) == "gold"


def test_recalculate_from_defaults_bronze():
    assert _recalculate_from_defaults(0) == "bronze"
    assert _recalculate_from_defaults(49) == "bronze"


def test_recalculate_from_defaults_silver():
    assert _recalculate_from_defaults(50) == "silver"


def test_recalculate_from_defaults_gold():
    assert _recalculate_from_defaults(200) == "gold"


# ──────────────────────────────────────────────────────────
# interaction_tasks.py — чистые функции
# ──────────────────────────────────────────────────────────

from app.tasks.interaction_tasks import (
    _resolve_to_inn,
    _drug_to_features,
    _predict_pair,
)

_MOCK_META = {
    "drug_classes": [
        "ACE_inhibitor", "ARB", "beta_blocker", "calcium_channel_blocker",
        "diuretic_thiazide", "diuretic_loop", "statin", "anticoagulant_warfarin",
        "anticoagulant_noac", "antiplatelet", "NSAID", "opioid",
        "benzo", "SSRI", "SNRI", "TCA", "antipsychotic_typical",
        "antipsychotic_atypical", "antibiotic_fluoroquinolone",
        "antibiotic_macrolide", "antibiotic_aminoglycoside",
        "antifungal_azole", "antiviral_HIV", "metformin",
        "sulfonylurea", "insulin", "thyroid_hormone", "digoxin",
        "PPI", "H2_blocker", "corticosteroid", "immunosuppressant",
        "antiepileptic_CYP_inducer", "antiepileptic_CYP_inhibitor",
    ],
    "severity_labels": {"0": "none", "1": "mild", "2": "moderate", "3": "severe", "4": "contraindicated"},
    "severity_descriptions": {
        "0": "Нет взаимодействия.", "1": "Лёгкое.", "2": "Умеренное.", "3": "Серьёзное.", "4": "Противопоказано.",
    },
    "severity_recommendations": {
        "0": "Продолжать.", "1": "Мониторинг.", "2": "Коррекция.", "3": "Замена.", "4": "Отменить.",
    },
}


def _make_mock_db(inn: str | None = None):
    db = MagicMock()
    if inn is not None:
        drug = MagicMock()
        drug.inn = inn
        db.execute.return_value.scalar_one_or_none.return_value = drug
    else:
        db.execute.return_value.scalar_one_or_none.return_value = None
    return db


def test_resolve_to_inn_found_in_db():
    db = _make_mock_db(inn="периндоприл")
    result = _resolve_to_inn("Нолипрел", db)
    assert result == "периндоприл"


def test_resolve_to_inn_not_found_returns_original():
    db = _make_mock_db(inn=None)
    result = _resolve_to_inn("НеизвестныйПрепарат", db)
    assert result == "НеизвестныйПрепарат"


def test_resolve_to_inn_db_exception_returns_original():
    db = MagicMock()
    db.execute.side_effect = Exception("DB error")
    result = _resolve_to_inn("Аспирин", db)
    assert result == "Аспирин"


def test_drug_to_features_warfarin():
    f = _drug_to_features("варфарин", _MOCK_META)
    assert f["drug_class"] == "anticoagulant_warfarin"
    assert f["bleeding_risk"] == 1
    assert f["cyp_inhibitor"] == 0


def test_drug_to_features_fluconazole():
    f = _drug_to_features("флуконазол", _MOCK_META)
    assert f["drug_class"] == "antifungal_azole"
    assert f["cyp_inhibitor"] == 1


def test_drug_to_features_clarithromycin():
    f = _drug_to_features("кларитромицин", _MOCK_META)
    assert f["drug_class"] == "antibiotic_macrolide"
    assert f["cyp_inhibitor"] == 1


def test_drug_to_features_ibuprofen():
    f = _drug_to_features("ибупрофен", _MOCK_META)
    assert f["drug_class"] == "NSAID"
    assert f["bleeding_risk"] == 1
    assert f["renal_risk"] == 1


def test_drug_to_features_metformin():
    f = _drug_to_features("метформин", _MOCK_META)
    assert f["drug_class"] == "metformin"
    assert f["bleeding_risk"] == 0
    assert f["qt_risk"] == 0


def test_drug_to_features_carbamazepine():
    f = _drug_to_features("карбамазепин", _MOCK_META)
    assert f["drug_class"] == "antiepileptic_CYP_inducer"
    assert f["cyp_inducer"] == 1


def test_drug_to_features_unknown_drug():
    f = _drug_to_features("неизвестный_препарат_xyz", _MOCK_META)
    assert f["drug_class"] == "unknown"
    assert f["cyp_inhibitor"] == 0
    assert f["bleeding_risk"] == 0


def test_predict_pair_returns_expected_fields():
    mock_model = MagicMock()
    mock_model.predict.return_value = [3]
    mock_model.predict_proba.return_value = [[0.05, 0.05, 0.1, 0.75, 0.05]]

    result = _predict_pair(mock_model, _MOCK_META, "варфарин", "ибупрофен")

    assert result["drug_a"] == "варфарин"
    assert result["drug_b"] == "ибупрофен"
    assert result["severity"] == "severe"
    assert "severity_score" in result
    assert "description" in result
    assert "recommendation" in result


def test_predict_pair_none_severity():
    mock_model = MagicMock()
    mock_model.predict.return_value = [0]
    mock_model.predict_proba.return_value = [[0.9, 0.05, 0.03, 0.01, 0.01]]

    result = _predict_pair(mock_model, _MOCK_META, "метформин", "омепразол")
    assert result["severity"] == "none"
    assert 0.0 <= result["severity_score"] <= 1.0


# ──────────────────────────────────────────────────────────
# billing_service.py — fallthrough и sync DB-функции
# ──────────────────────────────────────────────────────────

def test_compute_loyalty_level_empty_configs_returns_bronze():
    result = _compute_loyalty_level({}, 999)
    assert result == "bronze"


# ──────────────────────────────────────────────────────────
# billing_service.py — sync_deduct_credits (mock DB-сессия)
# ──────────────────────────────────────────────────────────

from app.services.billing_service import sync_deduct_credits


def _mock_user(balance: Decimal, monthly_checks: int = 5):
    user = MagicMock()
    user.balance = balance
    user.monthly_checks = monthly_checks
    user.loyalty_level = "bronze"
    return user


def _mock_sync_db(user):
    db = MagicMock()
    db.execute.return_value.scalar_one.return_value = user
    return db


def test_sync_deduct_credits_success():
    user = _mock_user(balance=Decimal("100"))
    db = _mock_sync_db(user)

    result = sync_deduct_credits(db, user_id=1, check_id=1, cost=Decimal("2"), description="test")

    assert result == Decimal("98")
    assert user.balance == Decimal("98")
    assert user.monthly_checks == 6
    db.flush.assert_called_once()


def test_sync_deduct_credits_increments_monthly_checks():
    user = _mock_user(balance=Decimal("50"), monthly_checks=49)
    db = _mock_sync_db(user)

    sync_deduct_credits(db, user_id=1, check_id=1, cost=Decimal("1"), description="test")
    assert user.monthly_checks == 50


def test_sync_deduct_credits_insufficient_balance():
    user = _mock_user(balance=Decimal("1"))
    db = _mock_sync_db(user)

    with pytest.raises(ValueError, match="Недостаточно кредитов"):
        sync_deduct_credits(db, user_id=1, check_id=1, cost=Decimal("5"), description="test")


def test_sync_deduct_credits_exact_balance():
    user = _mock_user(balance=Decimal("5"))
    db = _mock_sync_db(user)

    result = sync_deduct_credits(db, user_id=1, check_id=1, cost=Decimal("5"), description="test")
    assert result == Decimal("0")


def test_get_loyalty_configs_sync_empty_db():
    from app.services.billing_service import get_loyalty_configs_sync

    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = []
    result = get_loyalty_configs_sync(db)
    assert result == {}


def test_get_loyalty_configs_sync_with_rows():
    from app.services.billing_service import get_loyalty_configs_sync

    bronze = MagicMock()
    bronze.level = "bronze"
    silver = MagicMock()
    silver.level = "silver"

    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [bronze, silver]
    result = get_loyalty_configs_sync(db)
    assert "bronze" in result
    assert "silver" in result


# ──────────────────────────────────────────────────────────
# drug_service.py — fetch_from_grls (мок httpx)
# ──────────────────────────────────────────────────────────

import pytest


@pytest.mark.asyncio
async def test_fetch_from_grls_success():
    from unittest.mock import AsyncMock, patch
    from app.services.drug_service import fetch_from_grls

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [{"tradeName": "Нолипрел", "mnnName": "периндоприл", "atcCode": "C09BB04"}]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_from_grls("Нолипрел")

    assert result is not None
    assert result["inn"] == "периндоприл"
    assert result["atc_code"] == "C09BB04"


@pytest.mark.asyncio
async def test_fetch_from_grls_empty_data():
    from unittest.mock import AsyncMock, patch
    from app.services.drug_service import fetch_from_grls

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_from_grls("НеизвестноеНазвание")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_from_grls_non_200():
    from unittest.mock import AsyncMock, patch
    from app.services.drug_service import fetch_from_grls

    mock_response = MagicMock()
    mock_response.status_code = 503

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_from_grls("Аспирин")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_from_grls_network_error():
    import httpx
    from unittest.mock import AsyncMock, patch
    from app.services.drug_service import fetch_from_grls

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_from_grls("Аспирин")

    assert result is None


# ──────────────────────────────────────────────────────────
# interaction_tasks.py — _load_model (мок joblib и файловой системы)
# ──────────────────────────────────────────────────────────

def test_load_model_reads_model_and_meta(tmp_path):
    import json
    from unittest.mock import patch, mock_open
    import app.tasks.interaction_tasks as tasks_module

    # Сбрасываем глобальный кэш чтобы функция реально загрузила файл
    tasks_module._model = None
    tasks_module._meta = None

    fake_meta = {"drug_classes": ["statin"], "severity_labels": {"0": "none"}}
    fake_model = MagicMock()

    meta_content = json.dumps(fake_meta)

    with patch("app.tasks.interaction_tasks.joblib.load", return_value=fake_model) as mock_load, \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=meta_content)):

        model, meta = tasks_module._load_model()

    assert model is fake_model
    assert meta["drug_classes"] == ["statin"]
    mock_load.assert_called_once()

    # Второй вызов использует кэш (joblib.load не вызывается повторно)
    with patch("app.tasks.interaction_tasks.joblib.load") as mock_load2:
        model2, _ = tasks_module._load_model()
    mock_load2.assert_not_called()
    assert model2 is fake_model

    # Сбрасываем глобальное состояние после теста
    tasks_module._model = None
    tasks_module._meta = None
