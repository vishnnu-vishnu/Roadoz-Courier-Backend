import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PriorityLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketStatus:
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"



class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text(f"'{PriorityLevel.MEDIUM}'")
    )

    notify_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false")
    )

    subject: Mapped[str] = mapped_column(String(255), nullable=False)

    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text(f"'{TicketStatus.OPEN}'")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    
    order = relationship("Order", lazy="selectin")