from redis.asyncio import Redis
from packages.core.config import settings

_redis_client: Redis = None


async def init_redis() -> None:
    """Initialize Redis connection"""
    global _redis_client
    _redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        encoding="utf-8"
    )


async def close_redis() -> None:
    """Close Redis connection"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()


async def get_redis() -> Redis:
    """FastAPI dependency for Redis client"""
    return _redis_client
