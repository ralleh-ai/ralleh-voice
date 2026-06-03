# Deploy contract (v0 foundation)

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
- `GET /v1/readyz` -> `{ready:true, ...}`

## WS contract

- path: `/v1/ws/voice` (configurable)
- JSON event envelope with `type`, `session_id`, `seq`, `payload`

## Upgrade contract

Minor upgrades must preserve:
- health endpoint schema keys (`service`, `status`, `version`)
- event envelope top-level keys

Breaking event changes require explicit version bump (e.g. protocol `v1`).
