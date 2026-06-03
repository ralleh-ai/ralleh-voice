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

- authenticated WebSocket session setup (JWT or signed short-lived token)
- per-tenant/session authorization checks
- request rate limiting with identity/session awareness (size limits now exist but do not replace true rate limiting)
- transcript retention + redaction policy
- private-network or mTLS enforcement between voice app and OpenClaw bridge
- keep unauthenticated bridge mode disabled unless ingress is strictly private and controlled
- abuse controls for repeated reconnect/chunk flooding
