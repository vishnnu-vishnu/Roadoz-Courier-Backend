from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models.user import UserRole


class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.FRANCHISE


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    id: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        # Coerce string role → enum when coming from ORM
        if hasattr(obj, "role") and isinstance(obj.role, str):
            obj.__dict__["role"] = UserRole(obj.role)
        return super().model_validate(obj, *args, **kwargs)
