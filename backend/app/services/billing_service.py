from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User, LoyaltyConfig
from app.models.transaction import Transaction


LOYALTY_DISCOUNTS = {
    "bronze": Decimal("0"),
    "silver": Decimal("5"),
    "gold":   Decimal("15"),
}


def get_discount_percent(loyalty_level: str) -> Decimal:
    return LOYALTY_DISCOUNTS.get(loyalty_level, Decimal("0"))


def calculate_cost(loyalty_level: str) -> Decimal:
    discount = get_discount_percent(loyalty_level)
    return settings.CHECK_COST * (1 - discount / 100)


async def deduct_credits(
    db: AsyncSession,
    user_id: int,
    check_id: int,
    cost: Decimal,
    description: str,
) -> Decimal:
    result = await db.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = result.scalar_one()

    if user.balance < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Недостаточно кредитов. Баланс: {user.balance}, нужно: {cost}",
        )

    user.balance -= cost
    new_balance = user.balance

    transaction = Transaction(
        user_id=user_id,
        type="debit",
        amount=cost,
        balance_after=new_balance,
        description=description,
        check_id=check_id,
    )
    db.add(transaction)
    await db.flush()
    return new_balance


async def add_credits(
    db: AsyncSession,
    user_id: int,
    amount: Decimal,
    tx_type: str,
    description: str,
) -> Decimal:
    result = await db.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = result.scalar_one()
    user.balance += amount
    new_balance = user.balance

    transaction = Transaction(
        user_id=user_id,
        type=tx_type,
        amount=amount,
        balance_after=new_balance,
        description=description,
    )
    db.add(transaction)
    await db.flush()
    return new_balance


def recalculate_loyalty(monthly_checks: int) -> str:
    if monthly_checks >= settings.LOYALTY_GOLD_THRESHOLD:
        return "gold"
    if monthly_checks >= settings.LOYALTY_SILVER_THRESHOLD:
        return "silver"
    return "bronze"


# Sync-версия для Celery worker
def sync_deduct_credits(
    db: Session,
    user_id: int,
    check_id: int,
    cost: Decimal,
    description: str,
) -> Decimal:
    from sqlalchemy import select as sync_select

    user = db.execute(
        sync_select(User).where(User.id == user_id).with_for_update()
    ).scalar_one()

    if user.balance < cost:
        raise ValueError(f"Недостаточно кредитов. Баланс: {user.balance}, нужно: {cost}")

    user.balance -= cost
    user.monthly_checks += 1
    user.loyalty_level = recalculate_loyalty(user.monthly_checks)

    transaction = Transaction(
        user_id=user_id,
        type="debit",
        amount=cost,
        balance_after=user.balance,
        description=description,
        check_id=check_id,
    )
    db.add(transaction)
    db.flush()
    return user.balance
