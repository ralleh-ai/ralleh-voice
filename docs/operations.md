# Operations runbook (Phase 3)

## Process model

Single API service:
- FastAPI app with HTTP + WebSocket endpoints
- static browser MVP client (`/static`)

## Health checks

- `GET /v1/healthz` => liveness + selected adapter modes
- `GET /v1/readyz` => process/config readiness + per-adapter readiness flags
- In `openclaw-gateway` bridge mode, readiness is true only when bridge URL + agent target + token policy are satisfied.

## Logging

Current baseline: stdout logs + WebSocket event-level errors.

Recommended production posture:
- run behind Caddy,
- terminate TLS at edge,
- keep service loopback-bound,
- expose only reverse-proxy endpoint.

## Failure handling

- malformed JSON => `session.error` (`BAD_JSON`)
- invalid event envelope => `session.error` (`BAD_EVENT`)
- unsupported inbound type => `session.error` (`UNSUPPORTED_EVENT`)
- oversized websocket event => `session.error` (`EVENT_TOO_LARGE`)
- invalid/empty audio chunk => `session.error` (`BAD_AUDIO_CHUNK`)
- oversized decoded audio chunk => `session.error` (`AUDIO_CHUNK_TOO_LARGE`)
- per-turn chunk/byte limit exceeded => `session.error` (`TURN_BUFFER_OVERFLOW`) and turn buffer reset
- missing/failed auth in shared-secret mode => `session.error` (`AUTH_REQUIRED`/`AUTH_FAILED`)
- per-minute rate breach (events/audio bytes) => `session.error` (`RATE_LIMITED`) with structured `meta.kind`
- end-turn without chunks => `session.error` (`EMPTY_TURN`)
- adapter failure (missing dep/model/endpoint/auth/network/timeout/contract mismatch) => `session.error` (`ADAPTER_FAILURE`) with structured `meta`
- unexpected internal exception => `session.error` (`PIPELINE_FAILURE`) with generic detail
- cancel while a turn is active => `session.done` with `reason=cancelled`
- cancel with buffered-but-not-started audio => `session.done` with `reason=cancelled`

## Practical SLO starter targets

- health/readiness endpoint success > 99.9%
- median WS handshake < 250ms on LAN/VPS
- turn completion under 2.5s for short prompts after real model adapters are integrated

## Known MVP limitations

- deterministic adapters by default (real adapter modes are optional and may report not-ready)
- output "audio" is placeholder base64 text chunk, not playable PCM stream
- auth is shared-secret bootstrap only (no user identity/tenant claims yet)
- in-process rate limiter is single-instance only (no distributed coordination)
- no persistent transcript storage (intentionally minimal)
