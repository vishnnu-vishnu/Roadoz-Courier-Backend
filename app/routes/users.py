from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.role_checker import (
    get_current_user,
    require_add,
    require_edit,
    require_delete,
    require_view,
)
from app.models.user import User
from app.schemas.user_management import (
    ManagedUserCreate,
    ManagedUserUpdate,
    ManagedUserResponse,
    ManagedUserListResponse,
)
from app.services.user_service import (
    create_managed_user,
    list_managed_users,
    get_managed_user,
    update_managed_user,
    delete_managed_user,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=ManagedUserResponse, status_code=201)
async def create_user(
    data: ManagedUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_add),
):
    return await create_managed_user(db, current_user, data)


@router.get("", response_model=ManagedUserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_view),
):
    return await list_managed_users(db, current_user, page=page, limit=limit)


@router.get("/{user_id}", response_model=ManagedUserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_view),
):
    return await get_managed_user(db, current_user, user_id)


@router.put("/{user_id}", response_model=ManagedUserResponse)
async def update_user(
    user_id: str,
    data: ManagedUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_edit),
):
    return await update_managed_user(db, current_user, user_id, data)


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_delete),
):
    return await delete_managed_user(db, current_user, user_id)
