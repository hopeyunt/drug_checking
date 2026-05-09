from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, field_validator


class CheckRequest(BaseModel):
    drugs: list[str]

    @field_validator("drugs")
    @classmethod
    def at_least_two(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("Нужно минимум 2 препарата для проверки взаимодействия")
        if len(v) > 20:
            raise ValueError("Максимум 20 препаратов за один запрос")
        return [d.strip() for d in v]

    model_config = {
        "json_schema_extra": {
            "example": {"drugs": ["Нолипрел", "Метформин", "Аторвастатин"]}
        }
    }


class InteractionResult(BaseModel):
    drug_a: str
    drug_b: str
    severity: str          # none / mild / moderate / severe / contraindicated
    severity_score: float  # 0.0–1.0
    description: str
    recommendation: str


class CheckResponse(BaseModel):
    id: int
    status: str
    task_id: Optional[str] = None
    cost: Optional[Decimal] = None
    drugs_input: list[str]
    result: Optional[List[InteractionResult]] = None
    interactions_found: int = 0
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DrugSearchResult(BaseModel):
    id: int
    trade_name: str
    inn: str
    drug_class: Optional[str]
    atc_code: Optional[str]

    model_config = {"from_attributes": True}
