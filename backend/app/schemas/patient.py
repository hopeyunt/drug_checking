from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PatientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, examples=["Иванов Иван Иванович"])
    age: Optional[int] = Field(None, ge=0, le=120, examples=[67])
    weight_kg: Optional[float] = Field(None, gt=0, le=500, examples=[82.5])
    gfr: Optional[float] = Field(
        None, ge=0, le=200,
        description="Скорость клубочковой фильтрации, мл/мин/1.73м²",
        examples=[45.0],
    )
    diagnoses: list[str] = Field(default_factory=list, examples=[["I10", "E11.9"]])
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("diagnoses")
    @classmethod
    def limit_diagnoses(cls, v: list[str]) -> list[str]:
        if len(v) > 30:
            raise ValueError("Максимум 30 диагнозов")
        return [d.strip().upper() for d in v]


class PatientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    age: Optional[int] = Field(None, ge=0, le=120)
    weight_kg: Optional[float] = Field(None, gt=0, le=500)
    gfr: Optional[float] = Field(None, ge=0, le=200)
    diagnoses: Optional[List[str]] = None
    notes: Optional[str] = None


class PatientResponse(BaseModel):
    id: int
    user_id: int
    name: str
    age: Optional[int]
    weight_kg: Optional[float]
    gfr: Optional[float]
    diagnoses: list[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RenalRisk(str):
    NORMAL = "normal"        # СКФ ≥ 60
    MILD   = "mild"          # СКФ 45-59
    MODERATE = "moderate"    # СКФ 30-44
    SEVERE = "severe"        # СКФ 15-29
    FAILURE = "failure"      # СКФ < 15


def gfr_to_renal_risk(gfr: Optional[float]) -> str:
    if gfr is None:
        return RenalRisk.NORMAL
    if gfr >= 60:
        return RenalRisk.NORMAL
    if gfr >= 45:
        return RenalRisk.MILD
    if gfr >= 30:
        return RenalRisk.MODERATE
    if gfr >= 15:
        return RenalRisk.SEVERE
    return RenalRisk.FAILURE
