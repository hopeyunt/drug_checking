from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PatientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, examples=["Иванов Иван Иванович"])
    age: int | None = Field(None, ge=0, le=120, examples=[67])
    weight_kg: float | None = Field(None, gt=0, le=500, examples=[82.5])
    gfr: float | None = Field(
        None, ge=0, le=200,
        description="Скорость клубочковой фильтрации, мл/мин/1.73м²",
        examples=[45.0],
    )
    diagnoses: list[str] = Field(default_factory=list, examples=[["I10", "E11.9"]])
    notes: str | None = Field(None, max_length=2000)

    @field_validator("diagnoses")
    @classmethod
    def limit_diagnoses(cls, v: list[str]) -> list[str]:
        if len(v) > 30:
            raise ValueError("Максимум 30 диагнозов")
        return [d.strip().upper() for d in v]


class PatientUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    age: int | None = Field(None, ge=0, le=120)
    weight_kg: float | None = Field(None, gt=0, le=500)
    gfr: float | None = Field(None, ge=0, le=200)
    diagnoses: list[str] | None = None
    notes: str | None = None


class PatientResponse(BaseModel):
    id: int
    user_id: int
    name: str
    age: int | None
    weight_kg: float | None
    gfr: float | None
    diagnoses: list[str]
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RenalRisk(str):
    NORMAL = "normal"        # СКФ ≥ 60
    MILD   = "mild"          # СКФ 45-59
    MODERATE = "moderate"    # СКФ 30-44
    SEVERE = "severe"        # СКФ 15-29
    FAILURE = "failure"      # СКФ < 15


def gfr_to_renal_risk(gfr: float | None) -> str:
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
