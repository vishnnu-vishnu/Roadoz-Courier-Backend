from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    franchise_code: Optional[str] = None  # Required only for franchise login


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: UserRole


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class SendOTPRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    purpose: str = "login"  # login | password_reset | franchise_auth


class VerifyOTPRequest(BaseModel):
    identifier: str  # email or phone
    otp: str
    purpose: str = "login"


class OTPResponse(BaseModel):
    message: str
    expires_in: int  # seconds
