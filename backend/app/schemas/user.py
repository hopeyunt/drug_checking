from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    balance: Decimal
    loyalty_level: str
    monthly_checks: int
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TopUpRequest(BaseModel):
    amount: Decimal

    model_config = {"json_schema_extra": {"example": {"amount": 100}}}
