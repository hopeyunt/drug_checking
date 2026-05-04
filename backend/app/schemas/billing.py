from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel


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
