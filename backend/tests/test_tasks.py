import pytest
import numpy as np
from unittest.mock import MagicMock, patch


MOCK_META = {
    "drug_classes": [
        "ACE_inhibitor", "anticoagulant_warfarin", "NSAID", "SSRI",
        "antifungal_azole", "antibiotic_fluoroquinolone", "antiepileptic_CYP_inducer",
        "antibiotic_aminoglycoside", "TCA", "antipsychotic_typical",
        "antiepileptic_CYP_inhibitor", "antibiotic_macrolide", "statin",
    ],
    "severity_labels": {
        "0": "none", "1": "mild", "2": "moderate", "3": "severe", "4": "contraindicated"
    },
    "severity_descriptions": {
        "0": "Нет взаимодействия.", "2": "Умеренное взаимодействие.",
        "3": "Серьёзное взаимодействие.", "4": "Противопоказано."
    },
    "severity_recommendations": {
        "0": "Продолжайте приём.", "2": "Проконсультируйтесь с врачом.",
        "3": "Срочно к врачу.", "4": "Немедленно к врачу!"
    },
}


# ─────────────────── _drug_to_features ───────────────────

def test_features_warfarin_bleeding_risk():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("варфарин", MOCK_META)
    assert f["drug_class"] == "anticoagulant_warfarin"
    assert f["bleeding_risk"] == 1
    assert f["cyp_inhibitor"] == 0
    assert f["cyp_inducer"] == 0


def test_features_ibuprofen_nsaid():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("ибупрофен", MOCK_META)
    assert f["drug_class"] == "NSAID"
    assert f["bleeding_risk"] == 1
    assert f["renal_risk"] == 1


def test_features_fluconazole_cyp_inhibitor():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("флуконазол", MOCK_META)
    assert f["drug_class"] == "antifungal_azole"
    assert f["cyp_inhibitor"] == 1


def test_features_azithromycin_cyp_inhibitor():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("азитромицин", MOCK_META)
    assert f["cyp_inhibitor"] == 1


def test_features_carbamazepine_cyp_inducer():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("карбамазепин", MOCK_META)
    assert f["drug_class"] == "antiepileptic_CYP_inducer"
    assert f["cyp_inducer"] == 1


def test_features_ciprofloxacin_qt_risk():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("ципрофлоксацин", MOCK_META)
    assert f["qt_risk"] == 1


def test_features_haloperidol_qt_risk():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("галоперидол", MOCK_META)
    assert f["qt_risk"] == 1


def test_features_amitriptyline_qt_risk():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("амитриптилин", MOCK_META)
    assert f["qt_risk"] == 1


def test_features_gentamicin_renal_risk():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("гентамицин", MOCK_META)
    assert f["renal_risk"] == 1


def test_features_unknown_drug():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("абракадабра_неизвестный_xyz", MOCK_META)
    assert f["drug_class"] == "unknown"
    assert f["bleeding_risk"] == 0
    assert f["cyp_inhibitor"] == 0
    assert f["class_idx"] == 0


def test_features_class_idx_correct():
    from app.tasks.interaction_tasks import _drug_to_features
    f = _drug_to_features("флуконазол", MOCK_META)
    expected_idx = MOCK_META["drug_classes"].index("antifungal_azole")
    assert f["class_idx"] == expected_idx


# ─────────────────── _predict_pair ───────────────────

def _make_model(severity_idx: int, proba: list):
    model = MagicMock()
    model.predict.return_value = np.array([severity_idx])
    model.predict_proba.return_value = np.array([proba])
    return model


def test_predict_pair_moderate():
    from app.tasks.interaction_tasks import _predict_pair
    model = _make_model(2, [0.05, 0.1, 0.7, 0.1, 0.05])
    result = _predict_pair(model, MOCK_META, "варфарин", "ибупрофен")
    assert result["severity"] == "moderate"
    assert result["drug_a"] == "варфарин"
    assert result["drug_b"] == "ибупрофен"
    assert 0.0 <= result["severity_score"] <= 1.0
    assert result["description"] == "Умеренное взаимодействие."
    assert result["recommendation"] == "Проконсультируйтесь с врачом."


def test_predict_pair_none():
    from app.tasks.interaction_tasks import _predict_pair
    model = _make_model(0, [0.9, 0.05, 0.03, 0.01, 0.01])
    result = _predict_pair(model, MOCK_META, "омепразол", "метформин")
    assert result["severity"] == "none"


def test_predict_pair_severe():
    from app.tasks.interaction_tasks import _predict_pair
    model = _make_model(3, [0.02, 0.02, 0.1, 0.8, 0.06])
    result = _predict_pair(model, MOCK_META, "варфарин", "азитромицин")
    assert result["severity"] == "severe"


def test_predict_pair_same_class_flag():
    from app.tasks.interaction_tasks import _predict_pair
    model = _make_model(0, [0.9, 0.05, 0.03, 0.01, 0.01])
    _predict_pair(model, MOCK_META, "варфарин", "варфарин")
    features = model.predict.call_args[0][0]
    assert features[0][7] == 1  # same_class = 1


def test_predict_pair_different_class_flag():
    from app.tasks.interaction_tasks import _predict_pair
    model = _make_model(2, [0.05, 0.1, 0.7, 0.1, 0.05])
    _predict_pair(model, MOCK_META, "варфарин", "ибупрофен")
    features = model.predict.call_args[0][0]
    assert features[0][7] == 0  # different classes


# ─────────────────── loyalty_tasks ───────────────────

def _make_user(monthly_checks: int, current_level: str):
    user = MagicMock()
    user.monthly_checks = monthly_checks
    user.loyalty_level = current_level
    user.is_active = True
    return user


def test_recalculate_loyalty_upgrades_users():
    from app.tasks.loyalty_tasks import recalculate_all_loyalty_levels

    users = [
        _make_user(10, "bronze"),   # stays bronze
        _make_user(100, "bronze"),  # → silver
        _make_user(300, "silver"),  # → gold
    ]
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = users

    with patch("app.tasks.loyalty_tasks.get_sync_db", return_value=iter([mock_db])):
        result = recalculate_all_loyalty_levels()

    assert result["updated"] == 3
    assert result["status"] == "ok"
    assert users[0].loyalty_level == "bronze"
    assert users[1].loyalty_level == "silver"
    assert users[2].loyalty_level == "gold"
    for user in users:
        assert user.monthly_checks == 0
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


def test_recalculate_loyalty_no_users():
    from app.tasks.loyalty_tasks import recalculate_all_loyalty_levels

    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    with patch("app.tasks.loyalty_tasks.get_sync_db", return_value=iter([mock_db])):
        result = recalculate_all_loyalty_levels()

    assert result["updated"] == 0
    assert result["status"] == "ok"


def test_recalculate_loyalty_db_error_triggers_rollback():
    from app.tasks.loyalty_tasks import recalculate_all_loyalty_levels

    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("DB connection lost")

    with patch("app.tasks.loyalty_tasks.get_sync_db", return_value=iter([mock_db])):
        with pytest.raises(Exception, match="DB connection lost"):
            recalculate_all_loyalty_levels()

    mock_db.rollback.assert_called_once()
    mock_db.close.assert_called_once()
