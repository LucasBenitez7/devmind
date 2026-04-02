from typing import Any

from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url

from app.core.config import settings

_redis: Redis[Any] | None = None


async def get_redis() -> Redis[Any]:
    global _redis
    if _redis is None:
        _redis = redis_from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
