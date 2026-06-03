# Security Policy

## Supported Versions

This project is currently in early MVP stage (`0.2.x`) and only `main` is supported.

## Reporting a Vulnerability

Please report security issues privately to the maintainers (Ralleh AI team) and avoid posting exploit details in public issues.

When reporting, include:
- affected commit/version
- reproduction steps
- impact assessment
- suggested mitigation if available

## Security Posture (current)

- Caddy-first reverse proxy posture
- service binds loopback by default
- no secrets should be committed to git
- malformed WebSocket events are handled with structured errors
- websocket ingress has bounded event/chunk/turn limits to reduce abuse blast radius
- optional websocket auth bootstrap supports shared-secret and signed-token modes (`session.hello`)
- signed-token mode verifies HMAC signature and short-lived claims (`iat`, `exp`, `sid`, `clt`, optional `iss`/`aud`)
- websocket sliding-window rate limiting for events/audio-bytes with `memory` default and optional `redis` backend
- adapter failures are surfaced as structured errors without exposing token values
- unexpected internal pipeline exceptions are redacted to generic failure detail

## Current limitations (known)

- shared-secret mode remains static-token bootstrap (signed-token mode provides claim-bound expiry)
- redis limiter uses fixed-window buckets with atomic increment checks (not a full multi-window/token-bucket QoS model)
- deterministic placeholder adapters by default
- openclaw-gateway bridge mode uses pinned `POST /v1/chat/completions` gateway contract
- streaming mode reduces pre-processing buffering but is not yet true full-duplex adapter/model streaming
- bridge token values are runtime-only and must not appear in logs, tests, or error payloads

Do not deploy this MVP on a public internet endpoint without additional hardening.
