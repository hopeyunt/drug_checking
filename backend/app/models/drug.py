from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Drug(Base):
    __tablename__ = "drugs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Торговое название (русское), например "Нолипрел"
    trade_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # МНН — международное непатентованное наименование, например "периндоприл"
    inn: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Фармакологическая группа
    drug_class: Mapped[str] = mapped_column(String(255), nullable=True)
    # ATC-код (Anatomical Therapeutic Chemical)
    atc_code: Mapped[str] = mapped_column(String(20), nullable=True)
    # Источник: "grls" (из ГРЛС) или "drugbank" (из DrugBank)
    source: Mapped[str] = mapped_column(String(50), default="grls")
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_drugs_trade_name_lower", func.lower(trade_name)),
    )
