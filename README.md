# ralleh-voice

Browser-first voice gateway MVP for the Ralleh stack.

## Status

**Phase 1 MVP (implemented):**
- Browser/mobile mic capture using Web Audio ScriptProcessor fallback
- PCM16 mono chunking -> base64 -> WebSocket events
- Inbound event handling for `session.hello`, `audio.input.chunk`, `audio.input.end`, `session.cancel`
- Outbound events for `stt.final`, `agent.reply`, `audio.output.chunk`, `session.done`, `session.error`
- Structured malformed JSON / bad event errors (no process crash)
- Turn cancellation foundation with per-turn cancellation state
- Deterministic local adapters for VAD/STT/bridge/TTS so tests run without model downloads

**Not production telephony:**
- no PSTN/SIP/telephony ingress in this phase
- no authn/authz yet
- no real model-backed STT/TTS wired by default

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

Adapter mode hooks are present but currently deterministic by default:
- `RALLEH_VOICE_ADAPTER_VAD=deterministic|stub|silero`
- `RALLEH_VOICE_ADAPTER_STT=deterministic|stub|faster-whisper`
- `RALLEH_VOICE_ADAPTER_TTS=deterministic|stub|kokoro`
- `RALLEH_VOICE_ADAPTER_BRIDGE=deterministic|stub|openclaw-gateway`

Real adapter integrations are TODOs documented at boundaries in code/docs.

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
2. Real Silero/Faster-Whisper/Kokoro adapter wiring behind optional deps
3. OpenClaw bridge session cancellation propagation
4. Authenticated WS sessions + rate limits
5. Telephony transport adapters (separate phase, explicit non-goal here)

## Honest non-goals (for this phase)

- PSTN/SIP production calling
- high-availability multi-node media routing
- full compliance/PII retention stack

## Contributing & governance

- Contribution guide: `CONTRIBUTING.md`
- Changelog: `CHANGELOG.md`
- Security reporting: `SECURITY.md`
- License: `LICENSE` (MIT)
