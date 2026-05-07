from decimal import Decimal
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Numeric, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    yookassa_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    amount_rub: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    credits: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    confirmation_url: Mapped[str] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User")
