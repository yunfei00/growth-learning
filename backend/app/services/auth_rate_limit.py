"""Redis-backed authentication attempt limits with a bounded in-process fallback."""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


@dataclass
class _LocalCounter:
    count: int
    expires_at: float


async def _local_increment(request: Request, key: str, window: int) -> int:
    if not hasattr(request.app.state, "auth_rate_local"):
        request.app.state.auth_rate_local = {}
        request.app.state.auth_rate_lock = asyncio.Lock()
    async with request.app.state.auth_rate_lock:
        counters: dict[str, _LocalCounter] = request.app.state.auth_rate_local
        now = time.monotonic()
        current = counters.get(key)
        if current is None or current.expires_at <= now:
            counters[key] = _LocalCounter(1, now + window)
            if len(counters) > 10_000:
                request.app.state.auth_rate_local = {
                    item_key: item for item_key, item in counters.items() if item.expires_at > now
                }
            return 1
        current.count += 1
        return current.count


async def enforce_auth_rate_limit(
    request: Request, *, scope: str, identifier: str, limit: int
) -> None:
    settings = request.app.state.settings
    client_host = request.client.host if request.client else "unknown"
    digest = hashlib.sha256(f"{scope}:{client_host}:{identifier}".encode()).hexdigest()
    key = f"growth-learning:auth-rate:{digest}"
    count: int
    if settings.app_environment == "test":
        count = await _local_increment(request, key, settings.auth_rate_limit_window_seconds)
    else:
        try:
            if not hasattr(request.app.state, "auth_rate_redis"):
                request.app.state.auth_rate_redis = Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                )
            redis_client: Redis = request.app.state.auth_rate_redis
            count = int(await redis_client.incr(key))
            if count == 1:
                await redis_client.expire(key, settings.auth_rate_limit_window_seconds)
        except RedisError:
            logger.exception("Authentication rate limiter Redis failure; using local fallback")
            count = await _local_increment(request, key, settings.auth_rate_limit_window_seconds)
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="尝试次数过多，请稍后再试",
            headers={"Retry-After": str(settings.auth_rate_limit_window_seconds)},
        )
