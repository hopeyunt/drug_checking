from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field


class TransactionOut(BaseModel):
    id: int
    type: str
    amount: Decimal
    balance_after: Decimal
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceOut(BaseModel):
    balance: Decimal
    loyalty_level: str
    discount_percent: Decimal
    monthly_checks: int
    check_cost_with_discount: Decimal


class LoyaltyConfigOut(BaseModel):
    level: str
    min_predictions: int
    discount_percent: Decimal

    model_config = {"from_attributes": True}


class LoyaltyConfigUpdate(BaseModel):
    min_predictions: int = Field(..., ge=0, description="Минимум проверок в месяц для этого уровня")
    discount_percent: Decimal = Field(..., ge=0, le=100, description="Скидка в процентах (0–100)")


class PaymentCreateRequest(BaseModel):
    amount_rub: int = Field(..., description="Сумма в рублях (199, 499 или 1490)")

    model_config = {"json_schema_extra": {"example": {"amount_rub": 499}}}


class PaymentCreateResponse(BaseModel):
    payment_id: int
    yookassa_id: str
    confirmation_url: str
    credits: int
    amount_rub: int
    test_mode: bool = False


class PaymentOut(BaseModel):
    id: int
    yookassa_id: str
    amount_rub: Decimal
    credits: Decimal
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
