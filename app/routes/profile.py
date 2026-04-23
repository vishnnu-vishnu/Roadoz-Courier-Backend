import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.schemas.user import (
    UserResponse,
    UserUpdate,
    ChangePasswordRequest,
    OTPVerifyRequest,
    ProfileImageResponse,
)
from app.dependencies.role_checker import get_current_user
from app.models.user import User
from app.core.security import get_password_hash, verify_password
from app.utils.redis import cache_delete
from app.services.otp_service import send_otp, verify_otp
from app.dependencies.role_checker import require_permission

router = APIRouter(prefix="/profile", tags=["Profile"])

# Directory for storing uploaded profile images
UPLOAD_DIR = Path("uploads/profile_images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


# ── GET Profile ────────────────────────────────────────────────────────────────

@router.get("", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_permission("profile:view")),
):
    """Get the profile of the currently authenticated user. Password is never returned."""
    return UserResponse.model_validate(current_user)


# ── UPDATE Profile (name, phone, address, location) ───────────────────────────

@router.put("", response_model=UserResponse)
async def update_profile(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_permission("profile:edit")),
):
    """
    Update the authenticated user's profile.

    - **name** can be changed.
    - **email** cannot be changed here.
    - **password** is NOT accepted here — use `/profile/change-password`.
    - Updatable fields: name, phone, address, location.
    """
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await cache_delete(f"franchise:{current_user.id}")

    return UserResponse.model_validate(user)


# ── UPLOAD Profile Image ───────────────────────────────────────────────────────

@router.post("/upload-image", response_model=ProfileImageResponse)
async def upload_profile_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_permission("profile:edit")),
):
    """Upload a new profile image. Returns the stored file path/URL."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5 MB.",
        )

    # Generate a unique filename
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as f:
        f.write(contents)

    # Delete old image if exists
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    if user.profile_image:
        old_path = Path(user.profile_image.lstrip("/"))
        if old_path.exists():
            old_path.unlink(missing_ok=True)

    user.profile_image = f"/uploads/profile_images/{filename}"
    await db.flush()

    return ProfileImageResponse(profile_image=user.profile_image)


# ── GET Profile Image ──────────────────────────────────────────────────────────

@router.get("/image")
async def get_profile_image(
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_permission("profile:view")),
):
    """Get the current user's profile image URL."""
    if not current_user.profile_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile image uploaded yet.",
        )
    return {"profile_image": current_user.profile_image}


# ── CHANGE PASSWORD — Step 1: Submit old + new + confirm ──────────────────────

@router.post("/change-password/request")
async def change_password_request(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_permission("profile:edit")),
):
    """
    Step 1 of change-password flow.

    - Validates old password.
    - Validates new == confirm.
    - Sends OTP to user's email for confirmation.
    """
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirm password do not match.",
        )

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect.",
        )

    if data.old_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the old password.",
        )

    # Store the hashed new password temporarily in Redis via OTP purpose tag
    # We send OTP to email; the actual password change happens after OTP verification
    await send_otp(
        identifier=user.email,
        purpose="change_password",
        via="email",
    )

    from app.utils.redis import redis_set

    new_hash = get_password_hash(data.new_password)
    await redis_set(f"pending_pw:{user.email}", new_hash, expire=300)

    return {
        "message": "OTP sent to your registered email. Verify to complete password change.",
        "email": user.email,
    }


# ── CHANGE PASSWORD — Step 2: Validate OTP ────────────────────────────────────

@router.post("/change-password/verify")
async def change_password_verify(
    data: OTPVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_permission("profile:edit")),
):
    """
    Step 2 of change-password flow.

    - Validates OTP sent to email.
    - Applies the new hashed password.
    """
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    # Verify OTP (raises HTTPException on failure)
    await verify_otp(
        identifier=user.email,
        otp=data.otp,
        purpose="change_password",
    )

    from app.utils.redis import redis_get, redis_delete

    new_hash = await redis_get(f"pending_pw:{user.email}")
    await redis_delete(f"pending_pw:{user.email}")

    if not new_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change session expired. Please start over.",
        )

    user.password_hash = new_hash
    await db.flush()

    return {"message": "Password changed successfully."}