from dataclasses import dataclass

from ralleh_voice.config import load_settings
from ralleh_voice.rate_limits import DegradedRateLimiter, MemoryRateLimiter, RedisRateLimiter, build_rate_limiter


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, int] = {}

    @classmethod
    def from_url(cls, *_args, **_kwargs):
        return cls()

    def ping(self):
        return True

    def eval(self, _lua: str, _num_keys: int, key: str, increment: int, limit: int, _ttl: int):
        current = self.store.get(key, 0)
        if current + int(increment) > int(limit):
            return [0, current]
        current += int(increment)
        self.store[key] = current
        return [1, current]


@dataclass
class _FakeRedisModule:
    Redis: type = _FakeRedis


def test_memory_rate_limiter_per_identity():
    limiter = MemoryRateLimiter(window_seconds=60, event_limit=2, audio_bytes_limit=10)
    now = 100.0

    assert limiter.allow_event("a", now).allowed is True
    assert limiter.allow_event("a", now + 1).allowed is True
    blocked = limiter.allow_event("a", now + 2)
    assert blocked.allowed is False

    # Different identity should still pass.
    assert limiter.allow_event("b", now + 2).allowed is True


def test_memory_rate_limiter_audio_limit():
    limiter = MemoryRateLimiter(window_seconds=60, event_limit=10, audio_bytes_limit=5)
    now = 100.0

    assert limiter.allow_audio_bytes("a", 3, now).allowed is True
    denied = limiter.allow_audio_bytes("a", 3, now + 1)
    assert denied.allowed is False
    assert denied.observed == 3


def test_build_rate_limiter_redis_missing_dependency_degrades(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr("importlib.import_module", lambda _name: (_ for _ in ()).throw(ImportError("missing")))

    limiter = build_rate_limiter(load_settings())
    assert isinstance(limiter, DegradedRateLimiter)
    result = limiter.allow_event("id", 100)
    assert result.allowed is True
    assert result.degraded is True


def test_build_rate_limiter_redis_backend_with_fake_module(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr("importlib.import_module", lambda _name: _FakeRedisModule())

    limiter = build_rate_limiter(load_settings())
    assert isinstance(limiter, RedisRateLimiter)

    assert limiter.allow_event("x", 10).allowed is True
    assert limiter.allow_event("x", 10).allowed is True

    limiter.event_limit = 2
    denied = limiter.allow_event("x", 10)
    assert denied.allowed is False
