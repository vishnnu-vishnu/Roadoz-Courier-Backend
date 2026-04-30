import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    franchise_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("franchises.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    balance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    franchise = relationship("Franchise", lazy="selectin")
    transactions = relationship(
        "WalletTransaction", back_populates="wallet", cascade="all, delete-orphan", lazy="selectin",
        order_by="WalletTransaction.created_at.desc()",
    )


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    wallet_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    order_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # credit | debit
    type: Mapped[str] = mapped_column(String(10), nullable=False)

    opening_balance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    closing_balance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    description: Mapped[str] = mapped_column(String(500), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    wallet = relationship("Wallet", back_populates="transactions")
    order = relationship("Order", lazy="selectin")
