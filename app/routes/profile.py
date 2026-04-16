from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.schemas.user import UserResponse, UserUpdate
from app.dependencies.role_checker import get_current_user
from app.models.user import User
from app.core.security import get_password_hash
from app.utils.redis import cache_delete

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)


@router.put("", response_model=UserResponse)
async def update_profile(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the authenticated user's profile.

    Updatable fields: **name**, **phone**, **address**, **password**.
    """
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    update_data = data.model_dump(exclude_unset=True)

    if "password" in update_data:
        user.password_hash = get_password_hash(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()

    # Bust franchise cache if applicable
    await cache_delete(f"franchise:{current_user.id}")

    return UserResponse.model_validate(user)
