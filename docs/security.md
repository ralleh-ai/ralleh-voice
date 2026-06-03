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
- `.env.example` uses `*_REF` patterns for secret indirection.
- Service is intended to run behind Caddy with TLS termination at edge.

## Secret handling contract

Expected runtime secret delivery (via provisioning):
- OpenClaw gateway token reference/value at runtime only (used by optional `openclaw-gateway` bridge mode)
- optional TLS secrets if architecture changes (currently Caddy-first)

Secret material must never appear in:
- repository files,
- test fixtures,
- logs,
- committed generated artifacts.

## Pre-production hardening TODO

- authenticated WebSocket session setup (JWT or signed short-lived token)
- per-tenant/session authorization checks
- request rate limiting + payload-size limits
- transcript retention + redaction policy
- private-network or mTLS enforcement between voice app and OpenClaw bridge
- abuse controls for repeated reconnect/chunk flooding
