from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User, LoyaltyConfig
from app.models.transaction import Transaction


# Fallback-значения на случай пустой таблицы LoyaltyConfig в БД
_DEFAULT_CONFIGS = {
    "bronze": {"min_predictions": 0, "discount_percent": Decimal("0")},
    "silver": {"min_predictions": 50, "discount_percent": Decimal("5")},
    "gold": {"min_predictions": 200, "discount_percent": Decimal("15")},
}


# ─── Чистые вычислительные функции (без зависимости от БД) ───────────────────

def _compute_discount(configs: dict, level: str) -> Decimal:
    cfg = configs.get(level)
    if cfg is None:
        return Decimal("0")
    return cfg.discount_percent if hasattr(cfg, "discount_percent") else Decimal(str(cfg["discount_percent"]))


def _compute_cost(configs: dict, level: str) -> Decimal:
    discount = _compute_discount(configs, level)
    return settings.CHECK_COST * (1 - discount / 100)


def _compute_loyalty_level(configs: dict, monthly_checks: int) -> str:
    items = list(configs.values())
    sorted_levels = sorted(
        items,
        key=lambda c: c.min_predictions if hasattr(c, "min_predictions") else c["min_predictions"],
        reverse=True,
    )
    for cfg in sorted_levels:
        threshold = cfg.min_predictions if hasattr(cfg, "min_predictions") else cfg["min_predictions"]
        if monthly_checks >= threshold:
            return cfg.level if hasattr(cfg, "level") else [k for k, v in configs.items() if v is cfg][0]
    return "bronze"


# ─── Загрузка конфигов из БД ─────────────────────────────────────────────────

async def get_loyalty_configs(db: AsyncSession) -> dict[str, LoyaltyConfig]:
    result = await db.execute(select(LoyaltyConfig))
    rows = result.scalars().all()
    return {cfg.level: cfg for cfg in rows} if rows else {}


def get_loyalty_configs_sync(db: Session) -> dict[str, LoyaltyConfig]:
    result = db.execute(select(LoyaltyConfig))
    rows = result.scalars().all()
    return {cfg.level: cfg for cfg in rows} if rows else {}


# ─── Публичные async-функции для FastAPI эндпоинтов ──────────────────────────

async def get_discount_percent(db: AsyncSession, loyalty_level: str) -> Decimal:
    configs = await get_loyalty_configs(db)
    if not configs:
        return Decimal(str(_DEFAULT_CONFIGS.get(loyalty_level, {}).get("discount_percent", 0)))
    return _compute_discount(configs, loyalty_level)


async def calculate_cost(db: AsyncSession, loyalty_level: str) -> Decimal:
    configs = await get_loyalty_configs(db)
    if not configs:
        discount = Decimal(str(_DEFAULT_CONFIGS.get(loyalty_level, {}).get("discount_percent", 0)))
        return settings.CHECK_COST * (1 - discount / 100)
    return _compute_cost(configs, loyalty_level)


async def recalculate_loyalty(db: AsyncSession, monthly_checks: int) -> str:
    configs = await get_loyalty_configs(db)
    if not configs:
        return _recalculate_from_defaults(monthly_checks)
    return _compute_loyalty_level(configs, monthly_checks)


def recalculate_loyalty_sync(db: Session, monthly_checks: int) -> str:
    configs = get_loyalty_configs_sync(db)
    if not configs:
        return _recalculate_from_defaults(monthly_checks)
    return _compute_loyalty_level(configs, monthly_checks)


def _recalculate_from_defaults(monthly_checks: int) -> str:
    if monthly_checks >= settings.LOYALTY_GOLD_THRESHOLD:
        return "gold"
    if monthly_checks >= settings.LOYALTY_SILVER_THRESHOLD:
        return "silver"
    return "bronze"


# ─── Операции с балансом ─────────────────────────────────────────────────────

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
    user.loyalty_level = recalculate_loyalty_sync(db, user.monthly_checks)

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
