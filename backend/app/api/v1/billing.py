from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal

from app.core.database import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.schemas.user import TopUpRequest
from app.schemas.billing import TransactionOut, BalanceOut
from app.services.auth_service import get_current_user
from app.services.billing_service import add_credits, get_discount_percent, calculate_cost

router = APIRouter()


@router.get("/balance", response_model=BalanceOut)
async def get_balance(user: User = Depends(get_current_user)):
    discount = get_discount_percent(user.loyalty_level)
    cost = calculate_cost(user.loyalty_level)
    return BalanceOut(
        balance=user.balance,
        loyalty_level=user.loyalty_level,
        discount_percent=discount,
        monthly_checks=user.monthly_checks,
        check_cost_with_discount=cost,
    )


@router.post("/topup", response_model=BalanceOut)
async def top_up(
    body: TopUpRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.amount <= 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Сумма должна быть положительной")

    await add_credits(
        db, user.id, body.amount,
        tx_type="topup",
        description=f"Пополнение баланса на {body.amount} кредитов",
    )
    await db.commit()
    await db.refresh(user)

    discount = get_discount_percent(user.loyalty_level)
    return BalanceOut(
        balance=user.balance,
        loyalty_level=user.loyalty_level,
        discount_percent=discount,
        monthly_checks=user.monthly_checks,
        check_cost_with_discount=calculate_cost(user.loyalty_level),
    )


@router.get("/transactions", response_model=list[TransactionOut])
async def get_transactions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
