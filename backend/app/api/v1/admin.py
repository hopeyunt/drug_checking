from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.core.database import get_db
from app.models.user import User
from app.models.interaction import InteractionCheck
from app.models.transaction import Transaction
from app.schemas.user import UserOut
from app.services.auth_service import require_admin

router = APIRouter()


@router.get("/stats")
async def get_stats(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total_users = await db.execute(select(func.count(User.id)))
    total_checks = await db.execute(select(func.count(InteractionCheck.id)))
    completed_checks = await db.execute(
        select(func.count(InteractionCheck.id)).where(InteractionCheck.status == "completed")
    )
    total_revenue = await db.execute(
        select(func.sum(Transaction.amount)).where(Transaction.type == "topup")
    )
    total_spent = await db.execute(
        select(func.sum(Transaction.amount)).where(Transaction.type == "debit")
    )

    loyalty_dist = await db.execute(
        select(User.loyalty_level, func.count(User.id))
        .group_by(User.loyalty_level)
    )

    return {
        "total_users": total_users.scalar() or 0,
        "total_checks": total_checks.scalar() or 0,
        "completed_checks": completed_checks.scalar() or 0,
        "total_revenue_credits": float(total_revenue.scalar() or 0),
        "total_spent_credits": float(total_spent.scalar() or 0),
        "loyalty_distribution": {row[0]: row[1] for row in loyalty_dist.all()},
    }


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return result.scalars().all()
