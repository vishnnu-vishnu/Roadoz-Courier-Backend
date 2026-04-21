from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.user import User, UserRole
from app.models.franchise import Franchise
from app.core.security import verify_password
from app.utils.jwt import create_access_token, create_refresh_token
from app.schemas.auth import LoginRequest, TokenResponse, RoleCheckResponse


async def authenticate_user(db: AsyncSession, request: LoginRequest) -> TokenResponse:
    """Unified login for Super Admin and Franchise."""

    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    role = UserRole(user.role)  # coerce string → enum

    # Franchise-specific: require franchise_code
    if role == UserRole.FRANCHISE:
        if not request.franchise_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Franchise code is required for franchise login",
            )
        result = await db.execute(
            select(Franchise).where(
                Franchise.user_id == user.id,
                Franchise.franchise_code == request.franchise_code,
            )
        )
        franchise = result.scalar_one_or_none()
        if not franchise:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid franchise code")
        if not franchise.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Franchise account is disabled")

    token_data = {"user_id": user.id, "email": user.email, "role": role.value}

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        role=role,
    )


async def get_user_role_by_email(db: AsyncSession, email: str) -> RoleCheckResponse:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        return RoleCheckResponse(role=None, requires_franchise_code=False)

    role = UserRole(user.role)
    return RoleCheckResponse(role=role, requires_franchise_code=(role == UserRole.FRANCHISE))
