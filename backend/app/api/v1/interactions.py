from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.models.interaction import InteractionCheck
from app.schemas.interaction import CheckRequest, CheckResponse
from app.services.auth_service import get_current_user
from app.services.billing_service import calculate_cost
from app.tasks.interaction_tasks import run_interaction_check

router = APIRouter()


@router.post("/check", response_model=CheckResponse, status_code=202)
async def submit_check(
    body: CheckRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cost = await calculate_cost(db, user.loyalty_level)
    if user.balance < cost:
        raise HTTPException(
            status_code=402,
            detail=f"Недостаточно кредитов. Баланс: {user.balance}, стоимость проверки: {cost}",
        )

    check = InteractionCheck(
        user_id=user.id,
        drugs_input=body.drugs,
        status="pending",
        cost=cost,
    )
    db.add(check)
    await db.commit()
    await db.refresh(check)

    task = run_interaction_check.apply_async(
        args=[check.id],
        queue="interactions",
    )
    check.task_id = task.id
    await db.commit()
    await db.refresh(check)
    return check


@router.get("/check/{check_id}", response_model=CheckResponse)
async def get_check(
    check_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InteractionCheck).where(
            InteractionCheck.id == check_id,
            InteractionCheck.user_id == user.id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Проверка не найдена")
    return check


@router.get("/history", response_model=list[CheckResponse])
async def get_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    result = await db.execute(
        select(InteractionCheck)
        .where(InteractionCheck.user_id == user.id)
        .order_by(InteractionCheck.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
