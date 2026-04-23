import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")
