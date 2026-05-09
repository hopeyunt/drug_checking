import asyncio
import os
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.database import Base, get_db
import app.core.database as _db_module

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:changeme_in_prod@localhost:5432/drugcheck_test",
)


async def _ensure_test_db_exists(db_url: str) -> None:
    db_name = db_url.rsplit("/", 1)[-1]
    admin_url = db_url.rsplit("/", 1)[0] + "/postgres"
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            )
            if not result.scalar():
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    await _ensure_test_db_exists(TEST_DB_URL)
    engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await _seed_test_loyalty_configs(engine)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seed_test_loyalty_configs(engine):
    from decimal import Decimal
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models.user import LoyaltyConfig

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    configs = [
        LoyaltyConfig(level="bronze", min_predictions=0,   discount_percent=Decimal("0")),
        LoyaltyConfig(level="silver", min_predictions=50,  discount_percent=Decimal("5")),
        LoyaltyConfig(level="gold",   min_predictions=200, discount_percent=Decimal("15")),
    ]
    async with session_factory() as session:
        existing = await session.execute(select(LoyaltyConfig))
        if not existing.scalars().first():
            session.add_all(configs)
            await session.commit()


@pytest_asyncio.fixture
async def client(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncSession:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def mock_celery_task():
    """Мок Celery — тесты не требуют запущенного Redis-брокера."""
    mock_result = MagicMock()
    mock_result.id = "mock-task-id-for-tests"
    with patch(
        "app.tasks.interaction_tasks.run_interaction_check.apply_async",
        return_value=mock_result,
    ):
        yield


@pytest_asyncio.fixture(autouse=True)
async def redirect_app_session_local(db_engine):
    """Перенаправляет AsyncSessionLocal (health-check, sync-задачи) на тестовую БД."""
    test_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    original = _db_module.AsyncSessionLocal
    _db_module.AsyncSessionLocal = test_factory
    yield
    _db_module.AsyncSessionLocal = original


@pytest.fixture
def user_payload():
    import uuid
    return {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "testpassword123",
        "full_name": "Тест Пользователь",
    }
