import json
import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from fastapi import HTTPException, status
from app.models.user import User, UserRole
from app.models.franchise import Franchise
from app.schemas.franchise import FranchiseCreate, FranchiseUpdate, FranchiseResponse, FranchiseListResponse
from app.core.security import get_password_hash
from app.utils.redis import cache_set, cache_get, cache_delete
import uuid


async def create_franchise(db: AsyncSession, data: FranchiseCreate) -> FranchiseResponse:
    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Check franchise code uniqueness
    result = await db.execute(select(Franchise).where(Franchise.franchise_code == data.franchise_code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Franchise code already in use")

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        name=data.name,
        email=data.email,
        password_hash=get_password_hash(data.password),
        phone=data.phone,
        address=data.address,
        role=UserRole.FRANCHISE,
    )
    db.add(user)
    await db.flush()

    franchise = Franchise(
        id=str(uuid.uuid4()),
        user_id=user.id,
        franchise_code=data.franchise_code,
        name=data.name,
        email=data.email,
        phone=data.phone,
        address=data.address,
    )
    db.add(franchise)
    await db.flush()

    # Invalidate list cache
    await cache_delete("franchise_list")

    return FranchiseResponse.model_validate(franchise)


async def get_franchises(
    db: AsyncSession,
    page: int = 1,
    limit: int = 10,
    search: str = None,
) -> FranchiseListResponse:
    cache_key = f"franchise_list:{page}:{limit}:{search or ''}"
    cached = await cache_get(cache_key)
    if cached:
        data = json.loads(cached)
        return FranchiseListResponse(**data)

    query = select(Franchise)
    count_query = select(func.count()).select_from(Franchise)

    if search:
        filter_expr = or_(
            Franchise.name.ilike(f"%{search}%"),
            Franchise.email.ilike(f"%{search}%"),
            Franchise.phone.ilike(f"%{search}%"),
            Franchise.franchise_code.ilike(f"%{search}%"),
        )
        query = query.where(filter_expr)
        count_query = count_query.where(filter_expr)

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * limit
    result = await db.execute(query.offset(offset).limit(limit))
    franchises = result.scalars().all()

    response = FranchiseListResponse(
        items=[FranchiseResponse.model_validate(f) for f in franchises],
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total > 0 else 0,
    )

    await cache_set(cache_key, response.model_dump_json(), expire=120)
    return response


async def get_franchise_by_id(db: AsyncSession, franchise_id: str) -> FranchiseResponse:
    cache_key = f"franchise:{franchise_id}"
    cached = await cache_get(cache_key)
    if cached:
        return FranchiseResponse(**json.loads(cached))

    result = await db.execute(select(Franchise).where(Franchise.id == franchise_id))
    franchise = result.scalar_one_or_none()
    if not franchise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")

    resp = FranchiseResponse.model_validate(franchise)
    await cache_set(cache_key, resp.model_dump_json(), expire=300)
    return resp


async def update_franchise(db: AsyncSession, franchise_id: str, data: FranchiseUpdate) -> FranchiseResponse:
    result = await db.execute(select(Franchise).where(Franchise.id == franchise_id))
    franchise = result.scalar_one_or_none()
    if not franchise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(franchise, field, value)

    # Also update User record
    result = await db.execute(select(User).where(User.id == franchise.user_id))
    user = result.scalar_one_or_none()
    if user:
        for field in ["name", "phone", "address"]:
            if field in update_data:
                setattr(user, field, update_data[field])

    await db.flush()
    await cache_delete(f"franchise:{franchise_id}")
    await cache_delete("franchise_list")

    return FranchiseResponse.model_validate(franchise)


async def delete_franchise(db: AsyncSession, franchise_id: str) -> dict:
    result = await db.execute(select(Franchise).where(Franchise.id == franchise_id))
    franchise = result.scalar_one_or_none()
    if not franchise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")

    # Delete user (cascade deletes franchise)
    result = await db.execute(select(User).where(User.id == franchise.user_id))
    user = result.scalar_one_or_none()
    if user:
        await db.delete(user)

    await db.flush()
    await cache_delete(f"franchise:{franchise_id}")
    await cache_delete("franchise_list")

    return {"message": "Franchise deleted successfully"}
