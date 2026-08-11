"""Redis client construction."""

from redis.asyncio import Redis

from app.core.config import Settings, get_settings


def build_redis_client(settings: Settings | None = None) -> Redis:
    """Build a lazy async client; no network connection occurs here."""
    app_settings = settings or get_settings()
    return Redis.from_url(app_settings.redis_url, decode_responses=True)
