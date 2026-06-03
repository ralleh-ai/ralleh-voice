# ralleh-voice

Browser-first voice gateway MVP for the Ralleh stack.

## Status

**Phase 3 bridge contract (implemented):**
- Browser/mobile mic capture using Web Audio ScriptProcessor fallback
- PCM16 mono chunking -> base64 -> WebSocket events
- Inbound event handling for `session.hello`, `audio.input.chunk`, `audio.input.end`, `session.cancel`
- Outbound events for `stt.final`, `agent.reply`, `audio.output.chunk`, `session.done`, `session.error`
- Structured malformed JSON / bad event errors (no process crash)
- Turn cancellation foundation with per-turn cancellation state
- Adapter factory + explicit modules for VAD/STT/bridge/TTS
- Deterministic adapters remain default so tests run without model downloads
- Optional real adapters use lazy imports and fail with structured actionable errors
- OpenClaw bridge now uses a pinned local Gateway contract: `POST /v1/chat/completions`
- Bridge supports auth token via env var indirection, session-key routing header, deterministic error mapping, and contract-shape validation

**Not production telephony:**
- no PSTN/SIP/telephony ingress in this phase
- no authn/authz yet
- no real model-backed STT/TTS fully implemented yet (boundaries are wired, runtime integration is partial)

## Architecture

See `docs/architecture.md` for full details.

High level:

```text
Browser mic -> WS JSON events -> turn buffer -> VAD/STT/bridge/TTS adapters -> output events
```

## Quickstart (local)

```bash
cd ralleh-voice
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
uvicorn ralleh_voice.app:app --host 127.0.0.1 --port 8099 --reload
```

Open:
- API health: `http://127.0.0.1:8099/v1/healthz`
- Browser client: `http://127.0.0.1:8099/static/`

## Dev and test

Run tests:

```bash
.venv/bin/python -m pytest -q
```

Compile sanity check:

```bash
python3 -m compileall ralleh_voice tests
```

## Configuration

Environment variable based (`.env.example`, `ralleh_voice/config.py`).

Adapter mode selection (deterministic defaults are CI-safe):
- `RALLEH_VOICE_ADAPTER_VAD=deterministic|stub|silero`
- `RALLEH_VOICE_ADAPTER_STT=deterministic|stub|faster-whisper`
- `RALLEH_VOICE_ADAPTER_TTS=deterministic|stub|kokoro`
- `RALLEH_VOICE_ADAPTER_BRIDGE=deterministic|stub|openclaw-gateway`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789`
- `RALLEH_VOICE_OPENCLAW_AGENT_TARGET=openclaw/default`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN_ENV_VAR=RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN=<gateway bearer token>`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_ALLOW_UNAUTHENTICATED=false` (set true only for trusted private ingress)
- `RALLEH_VOICE_OPENCLAW_SESSION_KEY_PREFIX=ralleh-voice`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_TIMEOUT_MS=10000`

Optional heavy dependencies:

```bash
pip install -e .[voice]
```

Current real-adapter status:
- `silero` VAD: lazy optional dependency boundary + structured failure; full model bootstrap pending.
- `faster-whisper` STT: lazy optional dependency/model init boundary; streaming transcription wiring pending.
- `kokoro` TTS: lazy optional dependency boundary; synthesis wiring pending.
- `openclaw-gateway` bridge: real local HTTP integration to Gateway OpenAI-compatible endpoint (`/v1/chat/completions`).
- Bridge request contract:
  - header `Authorization: Bearer <token>` when token is configured
  - header `x-openclaw-session-key: <prefix>:<hashed-session-id>` for deterministic route continuity
  - body `{model:"openclaw/default"|"openclaw/<agent>", messages:[{role:"user",content:"..."}]}`
- Bridge response contract:
  - expects OpenAI-compatible `choices[0].message.content`
  - returns `CONTRACT_MISMATCH` when response schema is incompatible
- Bridge error contract:
  - `CONFIG_ERROR`, `AUTH_FAILED`, `TIMEOUT`, `NETWORK_ERROR`, `UNSUPPORTED_API`, `UPSTREAM_ERROR`, `CONTRACT_MISMATCH`
  - token values are never included in error payloads/log hints

When a selected adapter fails at runtime, WS returns `session.error` with code `ADAPTER_FAILURE` and structured metadata.

## Deployment posture

**Caddy-first**, loopback-bound app service.

Artifacts:
- `deploy/caddy/ralleh-voice.caddy`
- `deploy/systemd/ralleh-voice.service`
- `deploy/Dockerfile`
- `deploy/docker-compose.yml`

See `docs/deploy-contract.md`, `docs/operations.md`, and `docs/provisioning-integration.md`.

## Security posture

See `docs/security.md` and `SECURITY.md`.

Current repo policy:
- no secrets in git
- `.env` ignored
- deterministic local adapters for testability

## Roadmap (next slices)

1. AudioWorklet path + jitter buffering + playback improvements
2. Complete Silero/Faster-Whisper/Kokoro runtime audio wiring (beyond boundary/skeleton)
3. Authenticated WS sessions + rate limits
4. Telephony transport adapters (separate phase, explicit non-goal here)

## Honest non-goals (for this phase)

- PSTN/SIP production calling
- high-availability multi-node media routing
- full compliance/PII retention stack

## Contributing & governance

- Contribution guide: `CONTRIBUTING.md`
- Changelog: `CHANGELOG.md`
- Security reporting: `SECURITY.md`
- License: `LICENSE` (MIT)
