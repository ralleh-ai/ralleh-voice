# ralleh-provision integration (optional package)

`ralleh-voice` is optional for each client manifest.

## Proposed manifest extension

```yaml
spec:
  voice:
    enabled: true
    installMode: package # package | skip
    root: /opt/ralleh/ralleh-voice
    bind: 127.0.0.1:8099
    publicPath: /voice
    wsPath: /v1/ws/voice
    transport:
      mode: browser-websocket # browser-websocket | sip (future)
    adapters:
      vad: deterministic # deterministic | stub | silero
      stt: deterministic # deterministic | stub | faster-whisper
      tts: deterministic # deterministic | stub | kokoro
      openclawBridge: deterministic # deterministic | stub | openclaw-gateway
    secrets:
      - ref: secret:openclaw_gateway_token
        delivery:
          kind: systemd-env
          path: /etc/ralleh-voice/ralleh-voice.env
          mode: "0600"
    openclaw:
      gatewayUrl: http://127.0.0.1:18789
      agentTarget: openclaw/default
      tokenEnvVar: RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN
```

## Secret refs/delivery

No inline values in manifest. Use existing `spec.secrets` backend references and delivery model.

Minimum required secret refs when `enabled=true` (unless explicitly allowing unauthenticated private ingress):
- `secret:openclaw_gateway_token` for bridge auth

## Generated artifacts expected from provisioner

- `/opt/ralleh/ralleh-voice` checkout
- `/etc/ralleh-voice/ralleh-voice.env`
- `/etc/systemd/system/ralleh-voice.service`
- `/etc/caddy/conf.d/ralleh-voice.caddy` or an imported Caddy route snippet in the managed site block

## Verification checks expected from provisioner

1. `systemctl is-enabled ralleh-voice` == enabled
2. `systemctl is-active ralleh-voice` == active
3. `curl -fsS http://127.0.0.1:8099/v1/healthz` returns status ok
4. Caddy config validates (`caddy validate --config /etc/caddy/Caddyfile`)
5. reverse proxy route returns health endpoint over HTTPS/private ingress

## Non-goals for v0.2

- downloading large voice models during core provision by default
- forcing optional real adapters in CI/provision smoke checks
- PSTN phone service setup
- telephony compliance bundle
