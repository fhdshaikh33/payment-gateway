from redis.asyncio import Redis

from app.core.config import settings

# Global async Redis client
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

async def get_redis_client() -> Redis:
    """
    Dependency to get the Redis client.
    """
    return redis_client
