# Deploy contract (v0.2 phase-2 adapter wiring)

## Runtime artifact contract

Provisioning or install flow should produce:

1. app code checkout at `/opt/ralleh/ralleh-voice` (or chosen root)
2. virtualenv + package install
3. env file `/etc/ralleh-voice/ralleh-voice.env` (0600)
4. systemd unit `ralleh-voice.service`
5. reverse-proxy config (Caddy route snippet included)

## Listening/network contract

- service bind default: `127.0.0.1:8099`
- public exposure only through reverse proxy with TLS

## HTTP contract

- `GET /v1/healthz` -> `{status:"ok", ...}`
- `GET /v1/readyz` -> `{ready:<bool>, adapters:{...}, ...}`

## WS contract

- path: `/v1/ws/voice` (configurable)
- JSON event envelope with `type`, `session_id`, `seq`, `payload`
- inbound event set: `session.hello`, `audio.input.chunk`, `audio.input.end`, `session.cancel`
- outbound event set: `session.ready`, `stt.final`, `agent.reply`, `audio.output.chunk`, `session.done`, `session.error`
- malformed/unsupported events must return structured `session.error`

## Upgrade contract

Minor upgrades must preserve:
- health endpoint schema keys (`service`, `status`, `version`)
- event envelope top-level keys

Breaking event changes require explicit version bump (e.g. protocol `v1`).
