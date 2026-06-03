# Security model (Phase 4 production hardening)

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
- WebSocket auth mode supports `off`, `shared-secret`, and `signed-token` bootstraps.
- Signed-token mode verifies HMAC (`HS256`) signature and short-lived claims (`iat`, `exp`, `sid`, `clt`, optional `iss` and `aud`).
- Sliding-window ingress rate limiting supports `memory` (default) and optional Redis backend with atomic Lua increment checks.
- Redis backend is optional/lazy; missing dependency/connectivity degrades safely to memory with explicit metadata.
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

- token key rotation workflow (current signed-token contract supports short-lived expiry but no key-id rotation metadata)
- per-tenant/session authorization checks beyond session bootstrap claims
- richer limiter semantics (burst + sustained) and tenant quota policy
- transcript retention + redaction policy
- private-network or mTLS enforcement between voice app and OpenClaw bridge
- keep unauthenticated bridge mode disabled unless ingress is strictly private and controlled
- abuse controls for repeated reconnect/chunk flooding
