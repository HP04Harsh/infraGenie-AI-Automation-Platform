"""Redis cache layer for InfraGenie.

Provides async cache get/set with TTL, plus counters for monitoring.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger("cache")

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
DEFAULT_TTL = 300  # 5 minutes

_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        try:
            _pool = aioredis.from_url(REDIS_URL, decode_responses=True)
            await _pool.ping()
            logger.info("Connected to Redis at %s", REDIS_URL)
        except Exception as e:
            logger.warning("Redis unavailable, caching disabled: %s", e)
            return None
    return _pool


async def cache_get(key: str) -> Optional[Any]:
    r = await get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as e:
        logger.debug("Cache GET error: %s", e)
    return None


async def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        await r.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception as e:
        logger.debug("Cache SET error: %s", e)
        return False


async def cache_delete(key: str) -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        await r.delete(key)
        return True
    except Exception as e:
        logger.debug("Cache DEL error: %s", e)
        return False


async def cache_clear_pattern(pattern: str) -> int:
    r = await get_redis()
    if r is None:
        return 0
    try:
        keys = await r.keys(pattern)
        if keys:
            return await r.delete(*keys)
        return 0
    except Exception as e:
        logger.debug("Cache CLEAR error: %s", e)
        return 0
