from typing import Optional, List
from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, Text, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Скорость клубочковой фильтрации (мл/мин/1.73м²) — для коррекции доз
    gfr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Диагнозы по МКБ-10, например ["I10", "E11.9"]
    diagnoses: Mapped[list] = mapped_column(JSON, default=list)
    # Свободный текст: аллергии, особенности
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="patients")
