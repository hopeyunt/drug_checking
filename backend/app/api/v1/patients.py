from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse, gfr_to_renal_risk
from app.services.auth_service import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("", response_model=PatientResponse, status_code=201)
async def create_patient(
    body: PatientCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    patient = Patient(user_id=user.id, **body.model_dump())
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient


@router.get("", response_model=list[PatientResponse])
async def list_patients(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    result = await db.execute(
        select(Patient)
        .where(Patient.user_id == user.id)
        .order_by(Patient.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == user.id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return patient


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: int,
    body: PatientUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == user.id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)

    await db.commit()
    await db.refresh(patient)
    return patient


@router.delete("/{patient_id}", status_code=204)
async def delete_patient(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == user.id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    await db.delete(patient)
    await db.commit()


@router.get("/{patient_id}/renal-risk")
async def get_renal_risk(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == user.id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    risk = gfr_to_renal_risk(patient.gfr)
    return {
        "patient_id": patient_id,
        "gfr": patient.gfr,
        "renal_risk": risk,
        "note": _renal_risk_note(risk),
    }


def _renal_risk_note(risk: str) -> str:
    return {
        "normal":   "Коррекция дозы не требуется (СКФ ≥ 60 мл/мин)",
        "mild":     "Лёгкое снижение функции почек (СКФ 45–59). Мониторинг.",
        "moderate": "Умеренная почечная недостаточность (СКФ 30–44). Требуется коррекция дозы ряда препаратов.",
        "severe":   "Тяжёлая почечная недостаточность (СКФ 15–29). Обязательная коррекция доз.",
        "failure":  "Почечная недостаточность (СКФ < 15). Большинство нефротоксичных препаратов противопоказаны.",
    }.get(risk, "")
