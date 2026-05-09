import asyncio
import os
from decimal import Decimal
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User


async def create_admin():
    email = os.getenv("ADMIN_EMAIL", "admin@drugcheck.ru")
    password = os.getenv("ADMIN_PASSWORD", "admin1234")
    name = os.getenv("ADMIN_NAME", "Администратор")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            existing.is_admin = True
            await session.commit()
            print(f"Пользователь {email} назначен администратором.")
        else:
            user = User(
                email=email,
                hashed_password=hash_password(password),
                full_name=name,
                is_admin=True,
                is_active=True,
                balance=Decimal("0"),
            )
            session.add(user)
            await session.commit()
            print(f"Администратор создан: {email} / {password}")


if __name__ == "__main__":
    asyncio.run(create_admin())
