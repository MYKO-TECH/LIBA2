from redis.asyncio import Redis
import json
from datetime import timedelta, datetime
from .config import settings, cipher
import logging

logger = logging.getLogger(__name__)

redis = Redis.from_url(config.REDIS_URL)

async def get_session(user_id: str) -> dict:
    """Retrieve and decrypt user session"""
    try:
        encrypted_data = await redis.get(f"session:{user_id}")
        if encrypted_data:
            decrypted = cipher.decrypt(encrypted_data).decode()
            return json.loads(decrypted)
        return {}
    except Exception as e:
        logger.error(f"Session retrieval error: {str(e)}")
        return {}

async def update_session(user_id: str, data: dict) -> None:
    """Encrypt and store user session with TTL"""
    try:
        current = await get_session(user_id)
        merged = {**current, **data}
        encrypted = cipher.encrypt(json.dumps(merged).encode())
        await redis.setex(
            f"session:{user_id}",
            timedelta(seconds=config.SESSION_TTL),
            encrypted
        )
    except Exception as e:
        logger.error(f"Session update error: {str(e)}")

async def check_rate_limit(user_id: str) -> bool:
    """Redis-backed rate limiting"""
    try:
        current = await redis.incr(f"rate_limit:{user_id}")
        if current == 1:
            await redis.expire(f"rate_limit:{user_id}", 60)
        return current <= config.RATE_LIMIT
    except Exception as e:
        logger.error(f"Rate limit check error: {str(e)}")
        return False

async def log_security_event(user_id: str, event: str) -> None:
    """Store security events in Redis"""
    try:
        await redis.lpush(
            "security:events",
            f"{user_id}|{event}|{datetime.utcnow().isoformat()}"
        )
    except Exception as e:
        logger.error(f"Security log error: {str(e)}")
