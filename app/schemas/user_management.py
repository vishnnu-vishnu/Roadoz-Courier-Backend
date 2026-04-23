from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from app.models.user import UserRole


class UserPermissions(BaseModel):
    can_add: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_view: bool = True


class ManagedUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole
    phone: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None

    can_add: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_view: bool = True


class ManagedUserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

    can_add: Optional[bool] = None
    can_edit: Optional[bool] = None
    can_delete: Optional[bool] = None
    can_view: Optional[bool] = None


class ManagedUserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    role: UserRole

    can_add: bool
    can_edit: bool
    can_delete: bool
    can_view: bool

    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if hasattr(obj, "role") and isinstance(obj.role, str):
            obj.__dict__["role"] = UserRole(obj.role)
        return super().model_validate(obj, *args, **kwargs)


class ManagedUserListResponse(BaseModel):
    items: list[ManagedUserResponse]
    total: int
    page: int
    limit: int
    pages: int
