from redis.asyncio import Redis
from .settings import REDIS_URL

redis: Redis | None = None

async def get_redis() -> Redis:
    global redis
    if redis is None:
        redis = Redis.from_url(REDIS_URL, decode_responses=True)
    return redis

async def close_redis():
    global redis
    if redis is not None:
        await redis.close()
        redis = None
