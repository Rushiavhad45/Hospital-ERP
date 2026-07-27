from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import StockTxnType
from app.models.user import _enum


class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(120), unique=True, index=True)
    generic_name: Mapped[str] = mapped_column(sa.String(120), default="")
    category: Mapped[str] = mapped_column(sa.String(60), default="")     # Analgesic…
    manufacturer: Mapped[str] = mapped_column(sa.String(120), default="")
    unit: Mapped[str] = mapped_column(sa.String(20), default="tablet")
    unit_price: Mapped[int] = mapped_column(default=0)                   # ₹ per unit
    stock_quantity: Mapped[int] = mapped_column(default=0)
    reorder_level: Mapped[int] = mapped_column(default=10)
    batch_number: Mapped[str] = mapped_column(sa.String(40), default="")
    expiry_date: Mapped[date | None]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    transactions: Mapped[list["StockTransaction"]] = relationship(
        back_populates="medicine")

    @property
    def low_stock(self) -> bool:
        return self.stock_quantity <= self.reorder_level


class StockTransaction(Base):
    """Every stock movement, for a full pharmacy audit trail."""

    __tablename__ = "stock_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(sa.ForeignKey("medicines.id"), index=True)
    txn_type: Mapped[StockTxnType] = mapped_column(_enum(StockTxnType))
    quantity: Mapped[int]                                   # positive number
    balance_after: Mapped[int]
    reference: Mapped[str] = mapped_column(sa.String(120), default="")  # PO no / Rx / ward
    performed_by_user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)

    medicine: Mapped[Medicine] = relationship(back_populates="transactions")
