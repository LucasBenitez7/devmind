from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url

from app.core.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = redis_from_url(  # type: ignore[no-untyped-call]
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
