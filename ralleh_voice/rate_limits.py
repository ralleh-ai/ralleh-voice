from __future__ import annotations

import importlib
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .config import Settings


@dataclass(slots=True)
class RateLimitResult:
    allowed: bool
    observed: int
    backend: str
    degraded: bool = False
    detail: str | None = None


class RateLimiter:
    backend: str = "memory"

    def allow_event(self, identity: str, now: float) -> RateLimitResult:
        raise NotImplementedError

    def allow_audio_bytes(self, identity: str, chunk_size: int, now: float) -> RateLimitResult:
        raise NotImplementedError


@dataclass(slots=True)
class _IdentityWindow:
    event_timestamps: deque[float] = field(default_factory=deque)
    audio_chunks: deque[tuple[float, int]] = field(default_factory=deque)
    audio_bytes_in_window: int = 0


@dataclass(slots=True)
class MemoryRateLimiter(RateLimiter):
    window_seconds: int = 60
    event_limit: int = 600
    audio_bytes_limit: int = 8388608
    backend: str = "memory"
    identities: dict[str, _IdentityWindow] = field(default_factory=dict)

    def _state(self, identity: str) -> _IdentityWindow:
        return self.identities.setdefault(identity, _IdentityWindow())

    def _trim(self, state: _IdentityWindow, now: float) -> None:
        cutoff = now - self.window_seconds
        while state.event_timestamps and state.event_timestamps[0] <= cutoff:
            state.event_timestamps.popleft()
        while state.audio_chunks and state.audio_chunks[0][0] <= cutoff:
            _, size = state.audio_chunks.popleft()
            state.audio_bytes_in_window -= size

    def allow_event(self, identity: str, now: float) -> RateLimitResult:
        state = self._state(identity)
        self._trim(state, now)
        if len(state.event_timestamps) >= self.event_limit:
            return RateLimitResult(
                allowed=False,
                observed=len(state.event_timestamps),
                backend=self.backend,
            )
        state.event_timestamps.append(now)
        return RateLimitResult(allowed=True, observed=len(state.event_timestamps), backend=self.backend)

    def allow_audio_bytes(self, identity: str, chunk_size: int, now: float) -> RateLimitResult:
        state = self._state(identity)
        self._trim(state, now)
        proposed = state.audio_bytes_in_window + chunk_size
        if proposed > self.audio_bytes_limit:
            return RateLimitResult(
                allowed=False,
                observed=state.audio_bytes_in_window,
                backend=self.backend,
            )
        state.audio_chunks.append((now, chunk_size))
        state.audio_bytes_in_window = proposed
        return RateLimitResult(allowed=True, observed=state.audio_bytes_in_window, backend=self.backend)


@dataclass(slots=True)
class RedisRateLimiter(RateLimiter):
    redis_client: Any
    key_prefix: str
    window_seconds: int = 60
    event_limit: int = 600
    audio_bytes_limit: int = 8388608
    backend: str = "redis"

    _LUA_LIMIT = """
local key = KEYS[1]
local increment = tonumber(ARGV[1])
local max_limit = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

local current = redis.call('GET', key)
if current then
  current = tonumber(current)
else
  current = 0
end

if current + increment > max_limit then
  return {0, current}
end

local updated = redis.call('INCRBY', key, increment)
if updated == increment then
  redis.call('EXPIRE', key, ttl)
end

return {1, updated}
""".strip()

    def _bucket(self, now: float) -> int:
        return int(now) // self.window_seconds

    def _key(self, identity: str, kind: str, now: float) -> str:
        return f"{self.key_prefix}:{kind}:{identity}:{self._bucket(now)}"

    def _allow(self, key: str, *, increment: int, limit: int) -> RateLimitResult:
        allowed, observed = self.redis_client.eval(
            self._LUA_LIMIT,
            1,
            key,
            increment,
            limit,
            self.window_seconds + 1,
        )
        return RateLimitResult(
            allowed=bool(int(allowed)),
            observed=int(observed),
            backend=self.backend,
        )

    def allow_event(self, identity: str, now: float) -> RateLimitResult:
        return self._allow(self._key(identity, "events", now), increment=1, limit=self.event_limit)

    def allow_audio_bytes(self, identity: str, chunk_size: int, now: float) -> RateLimitResult:
        return self._allow(
            self._key(identity, "audio-bytes", now),
            increment=chunk_size,
            limit=self.audio_bytes_limit,
        )


@dataclass(slots=True)
class DegradedRateLimiter(RateLimiter):
    fallback: MemoryRateLimiter
    detail: str
    backend: str = "memory"

    def allow_event(self, identity: str, now: float) -> RateLimitResult:
        result = self.fallback.allow_event(identity, now)
        result.degraded = True
        result.detail = self.detail
        return result

    def allow_audio_bytes(self, identity: str, chunk_size: int, now: float) -> RateLimitResult:
        result = self.fallback.allow_audio_bytes(identity, chunk_size, now)
        result.degraded = True
        result.detail = self.detail
        return result


def build_rate_limiter(cfg: Settings) -> RateLimiter:
    memory = MemoryRateLimiter(
        window_seconds=cfg.ws_rate_limit_window_seconds,
        event_limit=cfg.ws_rate_limit_events_per_window,
        audio_bytes_limit=cfg.ws_rate_limit_audio_bytes_per_window,
    )

    if cfg.ws_rate_limit_backend == "memory":
        return memory

    try:
        redis_mod = importlib.import_module("redis")
    except ImportError:
        return DegradedRateLimiter(
            fallback=memory,
            detail="redis package not installed; using in-memory limiter",
        )

    try:
        client = redis_mod.Redis.from_url(
            cfg.ws_rate_limit_redis_url,
            socket_connect_timeout=max(1.0, cfg.ws_rate_limit_redis_timeout_ms / 1000.0),
            socket_timeout=max(1.0, cfg.ws_rate_limit_redis_timeout_ms / 1000.0),
            decode_responses=False,
        )
        client.ping()
    except Exception as exc:
        return DegradedRateLimiter(
            fallback=memory,
            detail=f"redis unavailable ({type(exc).__name__}); using in-memory limiter",
        )

    return RedisRateLimiter(
        redis_client=client,
        key_prefix=cfg.ws_rate_limit_redis_key_prefix,
        window_seconds=cfg.ws_rate_limit_window_seconds,
        event_limit=cfg.ws_rate_limit_events_per_window,
        audio_bytes_limit=cfg.ws_rate_limit_audio_bytes_per_window,
    )
