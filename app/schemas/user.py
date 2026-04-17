from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models.user import UserRole


class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.FRANCHISE


class UserUpdate(BaseModel):
    """Edit profile — name, phone, address, location only. Email & password NOT allowed here."""
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    profile_image: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if hasattr(obj, "role") and isinstance(obj.role, str):
            obj.__dict__["role"] = UserRole(obj.role)
        return super().model_validate(obj, *args, **kwargs)


# ── Change Password schemas ────────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


class OTPVerifyRequest(BaseModel):
    otp: str


class ProfileImageResponse(BaseModel):
    profile_image: str
    message: str = "Profile image updated successfully"