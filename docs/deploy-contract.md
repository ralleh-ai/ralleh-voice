# Deploy contract (v0.2.1 phase-3 OpenClaw bridge)

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
  - for `openclaw-gateway` bridge mode, readiness must include real bridge config availability (URL/agent target/token policy)

## WS contract

- path: `/v1/ws/voice` (configurable)
- JSON event envelope with `type`, `session_id`, `seq`, `payload`
- inbound event set: `session.hello`, `audio.input.chunk`, `audio.input.end`, `session.cancel`
- outbound event set: `session.ready`, `stt.final`, `agent.reply`, `audio.output.chunk`, `session.done`, `session.error`
- malformed/unsupported events must return structured `session.error`
- auth mode:
  - `RALLEH_VOICE_WS_AUTH_MODE=off` (default dev): no auth token required
  - `RALLEH_VOICE_WS_AUTH_MODE=shared-secret`: client must send `payload.auth_token` during `session.hello` before any audio input
- failed auth returns `session.error` (`AUTH_FAILED`) then socket close
- when auth is required, audio before hello/auth returns `session.error` (`AUTH_REQUIRED`)
- in-process rate limits emit `session.error` (`RATE_LIMITED`) with metadata; current implementation is one-process only

## Upgrade contract

Minor upgrades must preserve:
- health endpoint schema keys (`service`, `status`, `version`)
- event envelope top-level keys

Breaking event changes require explicit version bump (e.g. protocol `v1`).
