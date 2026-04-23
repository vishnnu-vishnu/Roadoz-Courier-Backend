import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    code: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    roles = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")
