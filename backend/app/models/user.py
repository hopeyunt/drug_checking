from decimal import Decimal
from datetime import datetime

from sqlalchemy import String, Boolean, Numeric, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    # Уровень лояльности: bronze / silver / gold
    loyalty_level: Mapped[str] = mapped_column(String(20), default="bronze")
    # Счётчик проверок за текущий месяц — для пересчёта уровня
    monthly_checks: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    transactions = relationship("Transaction", back_populates="user", lazy="select")
    checks = relationship("InteractionCheck", back_populates="user", lazy="select")


class LoyaltyConfig(Base):
    __tablename__ = "loyalty_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    min_predictions: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
