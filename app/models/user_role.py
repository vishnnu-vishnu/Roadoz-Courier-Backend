import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(Base):
    __tablename__ = "user_roles"

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_single_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    role = relationship("Role", back_populates="users")
    user = relationship("User")
