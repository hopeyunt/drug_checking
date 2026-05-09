"""Юнит-тесты для схем пациента и вспомогательной логики."""
import pytest
from pydantic import ValidationError

from app.schemas.patient import PatientCreate, PatientUpdate, gfr_to_renal_risk


# ── PatientCreate ──────────────────────────────────────────────────────────────

def test_patient_create_minimal():
    p = PatientCreate(name="Иванов И.И.")
    assert p.name == "Иванов И.И."
    assert p.age is None
    assert p.diagnoses == []


def test_patient_create_full():
    p = PatientCreate(
        name="Петров П.П.",
        age=67,
        weight_kg=82.5,
        gfr=45.0,
        diagnoses=["i10", "e11.9"],
        notes="Аллергия на пенициллин",
    )
    assert p.age == 67
    assert p.gfr == 45.0
    # Валидатор приводит к верхнему регистру
    assert "I10" in p.diagnoses
    assert "E11.9" in p.diagnoses


def test_patient_create_name_too_short():
    with pytest.raises(ValidationError):
        PatientCreate(name="А")


def test_patient_create_age_negative():
    with pytest.raises(ValidationError):
        PatientCreate(name="Иванов", age=-1)


def test_patient_create_age_over_limit():
    with pytest.raises(ValidationError):
        PatientCreate(name="Иванов", age=121)


def test_patient_create_weight_zero():
    with pytest.raises(ValidationError):
        PatientCreate(name="Иванов", weight_kg=0)


def test_patient_create_gfr_negative():
    with pytest.raises(ValidationError):
        PatientCreate(name="Иванов", gfr=-1.0)


def test_patient_create_too_many_diagnoses():
    with pytest.raises(ValidationError):
        PatientCreate(name="Иванов", diagnoses=[f"I{i:02d}" for i in range(31)])


def test_patient_create_diagnoses_uppercased():
    p = PatientCreate(name="Иванов", diagnoses=["i10", "e11"])
    assert p.diagnoses == ["I10", "E11"]


# ── PatientUpdate ──────────────────────────────────────────────────────────────

def test_patient_update_partial():
    u = PatientUpdate(age=70)
    assert u.age == 70
    assert u.name is None
    assert u.gfr is None


def test_patient_update_empty():
    u = PatientUpdate()
    dumped = u.model_dump(exclude_unset=True)
    assert dumped == {}


# ── gfr_to_renal_risk ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("gfr,expected", [
    (None,  "normal"),
    (90.0,  "normal"),
    (60.0,  "normal"),
    (59.9,  "mild"),
    (45.0,  "mild"),
    (44.9,  "moderate"),
    (30.0,  "moderate"),
    (29.9,  "severe"),
    (15.0,  "severe"),
    (14.9,  "failure"),
    (0.0,   "failure"),
])
def test_gfr_to_renal_risk(gfr, expected):
    assert gfr_to_renal_risk(gfr) == expected
