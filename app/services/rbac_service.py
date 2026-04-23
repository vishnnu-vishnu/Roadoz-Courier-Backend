import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User
from app.models.role import Role
from app.models.permission import Permission
from app.models.user_role import UserRole
from app.models.role_permission import RolePermission
from app.schemas.rbac_user import (
    UserCreateRequest,
    UserUpdateRequest,
    UserOut,
    UserListResponse,
)
from app.schemas.rbac_role import (
    RoleCreateRequest,
    RoleUpdateRequest,
    RoleOut,
    RoleWithPermissionsOut,
)
from app.schemas.rbac_permission import (
    PermissionCreateRequest,
    PermissionUpdateRequest,
    PermissionOut,
)


# -------------------- Users --------------------


async def create_user(db: AsyncSession, data: UserCreateRequest) -> UserOut:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        name=data.name,
        email=data.email,
        password_hash=get_password_hash(data.password),
        phone=data.phone,
        pincode=data.pincode,
        is_active=bool(data.is_active),
    )
    db.add(user)
    await db.flush()
    return UserOut.model_validate(user)


async def list_users(db: AsyncSession, page: int = 1, limit: int = 10) -> UserListResponse:
    count_query = select(func.count()).select_from(User)
    total = (await db.execute(count_query)).scalar_one()

    query = select(User).order_by(User.created_at.desc(), User.id.desc())
    offset = (page - 1) * limit
    result = await db.execute(query.offset(offset).limit(limit))
    users = result.scalars().all()

    return UserListResponse(
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total > 0 else 0,
    )


async def update_user(db: AsyncSession, user_id: str, data: UserUpdateRequest) -> UserOut:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    return UserOut.model_validate(user)


async def delete_user(db: AsyncSession, user_id: str) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.delete(user)
    await db.flush()
    return {"message": "User deleted successfully"}


# -------------------- Roles --------------------


async def create_role(db: AsyncSession, data: RoleCreateRequest) -> RoleWithPermissionsOut:
    result = await db.execute(select(Role).where(Role.name == data.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists")

    role = Role(id=str(uuid.uuid4()), name=data.name)
    db.add(role)
    await db.flush()

    if data.permission_codes:
        perms = (await db.execute(select(Permission).where(Permission.code.in_(data.permission_codes)))).scalars().all()
        found = {p.code for p in perms}
        missing = [c for c in data.permission_codes if c not in found]
        if missing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown permissions: {missing}")

        for p in perms:
            db.add(RolePermission(role_id=role.id, permission_id=p.id))
        await db.flush()

    return await get_role(db, role.id)


async def get_role(db: AsyncSession, role_id: str) -> RoleWithPermissionsOut:
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    perm_rows = await db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role.id)
        .where(Permission.is_active.is_(True))
    )
    permissions = [r[0] for r in perm_rows.all()]

    base = RoleWithPermissionsOut.model_validate(role)
    base.permissions = permissions
    return base


async def update_role(db: AsyncSession, role_id: str, data: RoleUpdateRequest) -> RoleWithPermissionsOut:
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data:
        role.name = update_data["name"]
    if "is_active" in update_data:
        role.is_active = bool(update_data["is_active"])

    if "permission_codes" in update_data and update_data["permission_codes"] is not None:
        codes = update_data["permission_codes"]
        perms = (await db.execute(select(Permission).where(Permission.code.in_(codes)))).scalars().all()
        found = {p.code for p in perms}
        missing = [c for c in codes if c not in found]
        if missing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown permissions: {missing}")

        await db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        for p in perms:
            db.add(RolePermission(role_id=role.id, permission_id=p.id))

    await db.flush()
    return await get_role(db, role.id)


async def delete_role(db: AsyncSession, role_id: str) -> dict:
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    await db.delete(role)
    await db.flush()
    return {"message": "Role deleted successfully"}


# -------------------- Permissions --------------------


async def create_permission(db: AsyncSession, data: PermissionCreateRequest) -> PermissionOut:
    result = await db.execute(select(Permission).where(Permission.code == data.code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission already exists")

    perm = Permission(
        id=str(uuid.uuid4()),
        code=data.code,
        module=data.module,
        action=data.action,
        description=data.description,
        is_active=bool(data.is_active),
    )
    db.add(perm)
    await db.flush()
    return PermissionOut.model_validate(perm)


async def list_permissions(db: AsyncSession) -> list[PermissionOut]:
    result = await db.execute(select(Permission).order_by(Permission.module.asc(), Permission.action.asc()))
    perms = result.scalars().all()
    return [PermissionOut.model_validate(p) for p in perms]


async def update_permission(db: AsyncSession, permission_id: str, data: PermissionUpdateRequest) -> PermissionOut:
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(perm, field, value)

    await db.flush()
    return PermissionOut.model_validate(perm)


async def delete_permission(db: AsyncSession, permission_id: str) -> dict:
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

    await db.delete(perm)
    await db.flush()
    return {"message": "Permission deleted successfully"}


# -------------------- Assign role --------------------


async def assign_role_to_user(db: AsyncSession, user_id: str, role_id: str) -> dict:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    existing = (await db.execute(select(UserRole).where(UserRole.user_id == user_id))).scalar_one_or_none()
    if existing:
        existing.role_id = role_id
    else:
        db.add(UserRole(user_id=user_id, role_id=role_id))

    await db.flush()
    return {"message": "Role assigned successfully"}
