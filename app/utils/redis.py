import json
from typing import Optional, Any
import redis.asyncio as aioredis
from app.core.config import settings

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def redis_set(key: str, value: Any, expire: int = 300) -> bool:
    """Set a value in Redis with expiry in seconds."""
    try:
        r = await get_redis()
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await r.set(key, serialized, ex=expire)
        return True
    except Exception:
        return False



async def redis_get(key: str) -> Optional[str]:
    """Get a value from Redis."""
    try:
        r = await get_redis()
        value = await r.get(key)

        if value is None:
            return None

        # 🔥 Fix: decode bytes → string
        if isinstance(value, bytes):
            return value.decode()

        return value

    except Exception:
        return None


async def redis_delete(key: str) -> bool:
    """Delete a key from Redis."""
    try:
        r = await get_redis()
        await r.delete(key)
        return True
    except Exception:
        return False


async def redis_exists(key: str) -> bool:
    """Check if a key exists in Redis."""
    try:
        r = await get_redis()
        return bool(await r.exists(key))
    except Exception:
        return False


# OTP helpers
OTP_PREFIX = "otp:"
BLACKLIST_PREFIX = "blacklist:"
CACHE_PREFIX = "cache:"


async def store_otp(identifier: str, purpose: str, otp: str) -> bool:
    key = f"{OTP_PREFIX}{purpose}:{identifier}"
    expire = settings.OTP_EXPIRE_MINUTES * 60
    return await redis_set(key, otp, expire=expire)


async def get_otp(identifier: str, purpose: str) -> Optional[str]:
    key = f"{OTP_PREFIX}{purpose}:{identifier}"
    return await redis_get(key)


async def delete_otp(identifier: str, purpose: str) -> bool:
    key = f"{OTP_PREFIX}{purpose}:{identifier}"
    return await redis_delete(key)


async def blacklist_token(token: str, expire: int = 3600) -> bool:
    key = f"{BLACKLIST_PREFIX}{token}"
    return await redis_set(key, "1", expire=expire)


async def is_token_blacklisted(token: str) -> bool:
    key = f"{BLACKLIST_PREFIX}{token}"
    return await redis_exists(key)


async def cache_set(key: str, value: Any, expire: int = 300) -> bool:
    return await redis_set(f"{CACHE_PREFIX}{key}", value, expire=expire)


async def cache_get(key: str) -> Optional[str]:
    return await redis_get(f"{CACHE_PREFIX}{key}")


async def cache_delete(key: str) -> bool:
    return await redis_delete(f"{CACHE_PREFIX}{key}")
