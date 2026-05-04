from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine

from app.core.config import settings


class Base(DeclarativeBase):
    pass


_async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
async_engine = create_async_engine(_async_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

sync_engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(sync_engine)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_db():
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_db():
    from app.models import user, drug, interaction, transaction  # noqa: F401
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_loyalty_configs()


async def _seed_loyalty_configs():
    from app.models.user import LoyaltyConfig
    from sqlalchemy import select
    from decimal import Decimal

    configs = [
        {"level": "bronze", "min_predictions": 0,   "discount_percent": Decimal("0")},
        {"level": "silver", "min_predictions": 50,  "discount_percent": Decimal("5")},
        {"level": "gold",   "min_predictions": 200, "discount_percent": Decimal("15")},
    ]
    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(LoyaltyConfig))
        if existing.scalars().first():
            return
        for c in configs:
            session.add(LoyaltyConfig(**c))
        await session.commit()
