import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.schemas.user_management import (
    ManagedUserCreate,
    ManagedUserUpdate,
    ManagedUserResponse,
    ManagedUserListResponse,
)


_ALLOWED_FRANCHISE_MANAGED_ROLES: set[UserRole] = {
    UserRole.ADMIN,
    UserRole.MANAGER,
    UserRole.SUPERVISOR,
    UserRole.USER,
}


def _assert_can_manage_target(current_user: User, target_user: User) -> None:
    current_role = UserRole(current_user.role)
    if current_role == UserRole.SUPER_ADMIN:
        return
    if current_role != UserRole.FRANCHISE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def _assert_create_role_allowed(current_user: User, role: UserRole) -> None:
    current_role = UserRole(current_user.role)
    if current_role == UserRole.SUPER_ADMIN:
        return

    if current_role == UserRole.FRANCHISE:
        if role not in _ALLOWED_FRANCHISE_MANAGED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Franchise cannot create this role",
            )
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to create users")


async def create_managed_user(db: AsyncSession, current_user: User, data: ManagedUserCreate) -> ManagedUserResponse:
    _assert_create_role_allowed(current_user, data.role)

    # email uniqueness
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    current_role = UserRole(current_user.role)

    user = User(
        id=str(uuid.uuid4()),
        name=data.name,
        email=data.email,
        password_hash=get_password_hash(data.password),
        phone=data.phone,
        address=data.address,
        location=data.location,
        role=data.role.value,
        can_add=bool(data.can_add),
        can_edit=bool(data.can_edit),
        can_delete=bool(data.can_delete),
        can_view=bool(data.can_view),
        is_active=True,
    )

    db.add(user)
    await db.flush()
    return ManagedUserResponse.model_validate(user)


async def list_managed_users(
    db: AsyncSession,
    current_user: User,
    page: int = 1,
    limit: int = 10,
) -> ManagedUserListResponse:
    current_role = UserRole(current_user.role)

    query = select(User).order_by(User.created_at.desc(), User.id.desc())
    count_query = select(func.count()).select_from(User)

    if current_role != UserRole.SUPER_ADMIN and current_role != UserRole.FRANCHISE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * limit
    result = await db.execute(query.offset(offset).limit(limit))
    users = result.scalars().all()

    return ManagedUserListResponse(
        items=[ManagedUserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total > 0 else 0,
    )


async def get_managed_user(db: AsyncSession, current_user: User, user_id: str) -> ManagedUserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _assert_can_manage_target(current_user, user)
    return ManagedUserResponse.model_validate(user)


async def update_managed_user(
    db: AsyncSession,
    current_user: User,
    user_id: str,
    data: ManagedUserUpdate,
) -> ManagedUserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _assert_can_manage_target(current_user, user)

    update_data = data.model_dump(exclude_unset=True)

    if "role" in update_data and update_data["role"] is not None:
        new_role: UserRole = update_data["role"]
        _assert_create_role_allowed(current_user, new_role)
        user.role = new_role.value

    for field in ("name", "phone", "address", "location", "is_active"):
        if field in update_data:
            setattr(user, field, update_data[field])

    for perm_field in ("can_add", "can_edit", "can_delete", "can_view"):
        if perm_field in update_data and update_data[perm_field] is not None:
            setattr(user, perm_field, bool(update_data[perm_field]))

    await db.flush()
    return ManagedUserResponse.model_validate(user)


async def delete_managed_user(db: AsyncSession, current_user: User, user_id: str) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _assert_can_manage_target(current_user, user)

    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")

    await db.delete(user)
    await db.flush()
    return {"message": "User deleted successfully"}
