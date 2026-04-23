from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import oauth2_scheme
from app.utils.jwt import verify_access_token
from app.utils.redis import is_token_blacklisted
from app.models.user import User, UserRole


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if await is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    payload = verify_access_token(token)
    if not payload:
        raise credentials_exception

    user_id: str = payload.get("user_id")
    if not user_id:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return user


async def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if UserRole(current_user.role) != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admin access required")
    return current_user


async def get_current_franchise(current_user: User = Depends(get_current_user)) -> User:
    if UserRole(current_user.role) != UserRole.FRANCHISE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Franchise access required")
    return current_user


def require_permission(action: str):
    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        role = UserRole(current_user.role)
        if role == UserRole.SUPER_ADMIN:
            return current_user

        flag_map = {
            "add": "can_add",
            "edit": "can_edit",
            "delete": "can_delete",
            "view": "can_view",
        }
        field = flag_map.get(action)
        if not field:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid permission action")
        if not bool(getattr(current_user, field, False)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{action.title()} permission required")
        return current_user

    return _checker


require_add = require_permission("add")
require_edit = require_permission("edit")
require_delete = require_permission("delete")
require_view = require_permission("view")
