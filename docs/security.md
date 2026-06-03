# Security model (Phase 2 adapter wiring)

## Principles

- No secrets committed to git.
- Config may include secret references, not secret values.
- Localhost/private-network by default.
- Keep retained voice data minimal by default.

## Current baseline

- HTTP health/readiness endpoints expose non-sensitive metadata.
- WebSocket event parser rejects malformed/unsupported payloads with structured errors.
- Adapter runtime failures are surfaced as structured `ADAPTER_FAILURE` events without leaking token values.
- Inbound WebSocket guardrails enforce max event/chunk/turn-buffer sizes to reduce abuse risk and memory pressure.
- Unexpected internal pipeline exceptions are redacted to generic `PIPELINE_FAILURE` details.
- Ingress guardrails bound websocket event size, per-chunk decoded audio size, and per-turn buffered chunks/bytes.
- Optional shared-secret WebSocket auth mode (`RALLEH_VOICE_WS_AUTH_MODE=shared-secret`) requires `session.hello` token bootstrap before audio is accepted.
- In-process sliding-window rate limiting covers inbound events/minute and audio bytes/minute with structured `RATE_LIMITED` errors.
- `.env.example` uses `*_REF` patterns for secret indirection.
- Service is intended to run behind Caddy with TLS termination at edge.

## Secret handling contract

Expected runtime secret delivery (via provisioning):
- OpenClaw gateway token reference/value at runtime only (used by optional `openclaw-gateway` bridge mode)
- Bridge token is sourced from environment variable indirection (`*_TOKEN_ENV_VAR`) and must never be logged or embedded in error payloads
- optional TLS secrets if architecture changes (currently Caddy-first)

Secret material must never appear in:
- repository files,
- test fixtures,
- logs,
- committed generated artifacts.

## Pre-production hardening TODO

- migrate shared-secret bootstrap to short-lived signed tokens (JWT or equivalent) with rotation and expiry
- per-tenant/session authorization checks
- replace process-local limiter with distributed identity/session-aware limiter (Redis or gateway-level)
- transcript retention + redaction policy
- private-network or mTLS enforcement between voice app and OpenClaw bridge
- keep unauthenticated bridge mode disabled unless ingress is strictly private and controlled
- abuse controls for repeated reconnect/chunk flooding
