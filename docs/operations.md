# Operations runbook (foundation)

## Process model

Single API service:
- FastAPI app with HTTP + WebSocket endpoints
- static debug client optional (`/static`)

## Health checks

- `GET /v1/healthz` => liveness + component mode
- `GET /v1/readyz` => readiness of process/config

## Logging

Use structured stdout logging (TODO: add explicit logger middleware).

Recommended immediate production setup:
- run behind Caddy,
- terminate TLS at edge,
- keep service loopback-bound,
- expose only reverse-proxy endpoint.

## Suggested SLO starter targets

- health/readiness endpoint success > 99.9%
- median WS handshake < 250ms on LAN/VPS
- turn completion under 2.5s for short prompts (after real models integrated)

## Failure handling

- unsupported events return `session.error`
- malformed JSON should return structured error (TODO)
- adapter/model failures should map to consistent error codes (TODO)
