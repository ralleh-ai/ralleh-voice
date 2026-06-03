# Security model (foundation)

## Principles

- No secrets committed to git.
- Manifests and config may include secret references, not secret values.
- Localhost/private-network by default.
- Minimize retained audio/transcript data until policy is explicit.

## Current baseline

- HTTP health endpoints only expose non-sensitive process metadata.
- WebSocket auth is TODO (do not expose publicly as-is).
- `.env.example` uses `*_REF` patterns for secret indirection.

## Secret handling contract

Expected runtime secret delivery (via provisioning):
- OpenClaw gateway token (reference only in app config)
- optional TLS key/cert if terminating in app (currently expect Caddy fronting)

No secret material should appear in:
- repository files,
- logs,
- test fixtures,
- generated examples committed to git.

## Pre-production hardening TODO

- authenticated WebSocket session setup (JWT or signed short-lived token)
- per-tenant/session authorization checks
- request rate limiting / abuse controls
- payload-size limits and malformed-frame handling
- transcript retention policy + redaction pipeline
- mTLS/private network enforcement between voice app and OpenClaw bridge
