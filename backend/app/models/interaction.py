from decimal import Decimal
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Text, Numeric, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InteractionCheck(Base):
    __tablename__ = "interaction_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Список препаратов на входе (JSON-массив названий)
    drugs_input: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Статус: pending / processing / completed / failed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # Результат — список найденных взаимодействий
    result: Mapped[dict] = mapped_column(JSON, nullable=True)
    # Сколько взаимодействий нашли
    interactions_found: Mapped[int] = mapped_column(Integer, default=0)
    # Celery task id
    task_id: Mapped[str] = mapped_column(String(255), nullable=True)
    # Стоимость проверки (с учётом скидки по лояльности)
    cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="checks")
