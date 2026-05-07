from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal

from app.core.database import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.models.payment import Payment
from app.schemas.user import TopUpRequest
from app.schemas.billing import (
    TransactionOut, BalanceOut,
    PaymentCreateRequest, PaymentCreateResponse, PaymentOut,
)
from app.services.auth_service import get_current_user
from app.services.billing_service import add_credits, get_discount_percent, calculate_cost
from app.services import yookassa_service

router = APIRouter()

ALLOWED_AMOUNTS = {199, 499, 1490}
AMOUNT_TO_CREDITS = {199: 50, 499: 150, 1490: 500}


@router.get("/balance", response_model=BalanceOut)
async def get_balance(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    discount = await get_discount_percent(db, user.loyalty_level)
    cost = await calculate_cost(db, user.loyalty_level)
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
        raise HTTPException(status_code=400, detail="Сумма должна быть положительной")

    await add_credits(
        db, user.id, body.amount,
        tx_type="topup",
        description=f"Пополнение баланса на {body.amount} кредитов",
    )
    await db.commit()
    await db.refresh(user)

    discount = await get_discount_percent(db, user.loyalty_level)
    cost = await calculate_cost(db, user.loyalty_level)
    return BalanceOut(
        balance=user.balance,
        loyalty_level=user.loyalty_level,
        discount_percent=discount,
        monthly_checks=user.monthly_checks,
        check_cost_with_discount=cost,
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


@router.post("/payment/create", response_model=PaymentCreateResponse)
async def create_payment(
    body: PaymentCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.amount_rub not in ALLOWED_AMOUNTS:
        raise HTTPException(
            status_code=400,
            detail=f"Допустимые суммы: {sorted(ALLOWED_AMOUNTS)} рублей",
        )

    credits = Decimal(AMOUNT_TO_CREDITS[body.amount_rub])

    try:
        result = await yookassa_service.create_payment(body.amount_rub, user.id, int(credits))
    except Exception:
        raise HTTPException(status_code=502, detail="Ошибка платёжного шлюза. Попробуйте позже.")

    payment = Payment(
        user_id=user.id,
        yookassa_id=result["yookassa_id"],
        amount_rub=Decimal(body.amount_rub),
        credits=credits,
        status="pending",
        confirmation_url=result["confirmation_url"],
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return PaymentCreateResponse(
        payment_id=payment.id,
        yookassa_id=payment.yookassa_id,
        confirmation_url=payment.confirmation_url,
        credits=int(credits),
        amount_rub=body.amount_rub,
        test_mode=result.get("test_mode", False),
    )


@router.post("/payment/webhook", status_code=200)
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    signature = request.headers.get("X-Signature", "")

    if not yookassa_service.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=400, detail="Неверная подпись webhook")

    event = yookassa_service.parse_webhook(body)
    if not event:
        return {"ok": True}

    result = await db.execute(
        select(Payment).where(Payment.yookassa_id == event["yookassa_id"])
    )
    payment = result.scalar_one_or_none()
    if not payment or payment.status == "succeeded":
        return {"ok": True}

    payment.status = "succeeded"
    await add_credits(
        db,
        user_id=payment.user_id,
        amount=payment.credits,
        tx_type="topup",
        description=f"Оплата {payment.amount_rub} ₽ → {payment.credits} кредитов",
    )
    await db.commit()
    return {"ok": True}


@router.get("/payment/stub")
async def payment_stub(id: str, db: AsyncSession = Depends(get_db)):
    """Только для режима разработки — симулирует успешную оплату."""
    result = await db.execute(
        select(Payment).where(Payment.yookassa_id == id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    if payment.status == "succeeded":
        return {"message": "Кредиты уже начислены", "credits": float(payment.credits)}

    payment.status = "succeeded"
    await add_credits(
        db,
        user_id=payment.user_id,
        amount=payment.credits,
        tx_type="topup",
        description=f"[Тест] Оплата {payment.amount_rub} ₽ → {payment.credits} кредитов",
    )
    await db.commit()
    return {"message": "Кредиты начислены (тестовый режим)", "credits": float(payment.credits)}


@router.get("/payments", response_model=list[PaymentOut])
async def get_payments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
):
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
