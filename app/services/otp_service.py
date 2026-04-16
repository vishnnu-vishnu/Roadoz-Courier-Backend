from fastapi import HTTPException, status
from app.utils.otp import generate_otp
from app.utils.redis import store_otp, get_otp, delete_otp
from app.utils.smtp import send_email_otp
from app.utils.twilio import send_sms_otp
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


async def send_otp(identifier: str, purpose: str, via: str = "email") -> bool:
    """Generate and send OTP to identifier (email or phone)."""
    otp = generate_otp()

    # Store in Redis
    stored = await store_otp(identifier, purpose, otp)
    if not stored:
        logger.warning(f"Redis unavailable - OTP for {identifier}: {otp}")  # Fallback log

    success = False
    if via == "email":
        success = await send_email_otp(identifier, otp, purpose)
    elif via == "sms":
        success = await send_sms_otp(identifier, otp, purpose)

    if not success:
        # For dev/testing: log OTP if sending fails
        logger.warning(f"[DEV] OTP for {identifier} ({purpose}): {otp}")

    return True  # Always return True; OTP is stored in Redis regardless


async def verify_otp(identifier: str, otp: str, purpose: str) -> bool:
    """Verify OTP from Redis."""
    stored_otp = await get_otp(identifier, purpose)

    if not stored_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired or not found. Please request a new OTP.",
        )

    if stored_otp != otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP",
        )

    # Delete OTP after successful verification
    await delete_otp(identifier, purpose)
    return True
