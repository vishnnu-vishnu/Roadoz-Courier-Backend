import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_sms_otp(phone: str, otp: str, purpose: str = "login") -> bool:
    """Send OTP via Twilio SMS."""
    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"Your OTP for {purpose} is: {otp}. Expires in {settings.OTP_EXPIRE_MINUTES} minutes.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone,
        )
        logger.info(f"SMS OTP sent to {phone}, SID: {message.sid}")
        return True
    except ImportError:
        logger.warning("Twilio not installed. Install with: pip install twilio")
        return False
    except Exception as e:
        logger.error(f"Failed to send SMS OTP: {e}")
        return False
