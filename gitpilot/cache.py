"""Caching layer: Redis when configured, in-memory otherwise.

Both backends expose the same tiny interface (get/set with TTL), so the
rest of the app never cares which one is active. That swap-ability is
the 'cache-aside' story you tell in the interview.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from . import config


class MemoryCache:
    """Zero-dependency cache with TTL. Perfect for a single-server demo."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, payload = item
        if time.time() > expires_at:
            del self._store[key]
            return None
        return json.loads(payload)

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self._store[key] = (time.time() + ttl_seconds, json.dumps(value))


class RedisCache:
    """Shared cache for multi-server setups."""

    def __init__(self, url: str) -> None:
        import redis  # lazy import: the app still runs if redis is absent

        self._client = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> Any | None:
        payload = self._client.get(key)
        return json.loads(payload) if payload else None

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self._client.set(key, json.dumps(value), ex=ttl_seconds)


_cache = None


def get_cache():
    """Singleton. Falls back to memory if Redis is unconfigured or down."""
    global _cache
    if _cache is not None:
        return _cache
    if config.REDIS_URL:
        try:
            candidate = RedisCache(config.REDIS_URL)
            candidate.set("gitpilot:healthcheck", "ok", ttl_seconds=5)
            _cache = candidate
        except Exception:
            _cache = MemoryCache()
    else:
        _cache = MemoryCache()
    return _cache


def make_key(*parts: str) -> str:
    """Stable, opaque cache key from arbitrary parts (prompt, model, ...)."""
    raw = "||".join(parts)
    return "gitpilot:" + hashlib.sha256(raw.encode()).hexdigest()
