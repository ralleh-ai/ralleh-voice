# ralleh-voice

Browser-first voice gateway MVP for the Ralleh stack.

## Status

**Phase 4.1 Control Room UX polish (implemented):**
- Polished browser "Control Room" UI with responsive cards/panels for agent target, voice profile, conversation mode, performance mode, barge-in sensitivity, and chunk tuning profiles
- Live microphone waveform/level meter with RMS/peak/clipping warnings
- Timeline-style transcript/reply/event feed plus collapsible protocol debug stream
- Session/connection/reconnect/latency/resource counters with client-side instrumentation
- Local preference persistence for safe UI settings (`localStorage`) without persisting auth tokens
- Browser/mobile mic capture using Web Audio ScriptProcessor fallback
- PCM16 mono chunking -> base64 -> WebSocket events
- Inbound event handling for `session.hello`, `audio.input.chunk`, `audio.input.end`, `session.cancel`
- Outbound events for `stt.partial`, `stt.final`, `agent.reply`, `audio.output.chunk`, `session.done`, `session.error`
- Short-lived HMAC signed-token auth mode (`RALLEH_VOICE_WS_AUTH_MODE=signed-token`) with expiry + claims checks
- Optional distributed rate limiter backend (`memory` default, `redis` optional/lazy)
- Streaming processing mode (`RALLEH_VOICE_WS_PROCESSING_MODE=streaming`) with bounded pending queue and early turn start
- Structured malformed JSON / bad event errors (no process crash)
- Input guardrails for inbound event size, per-chunk size, and total buffered-audio limits
- Turn cancellation foundation with per-turn cancellation state
- Adapter factory + explicit modules for VAD/STT/bridge/TTS
- Deterministic adapters remain default so tests run without model downloads
- Optional real adapters use lazy imports and fail with structured actionable errors
- OpenClaw bridge now uses a pinned local Gateway contract: `POST /v1/chat/completions`
- Bridge supports auth token via env var indirection, session-key routing header, deterministic error mapping, and contract-shape validation

**Not production telephony:**
- no PSTN/SIP/telephony ingress in this phase
- no real model-backed STT/TTS fully implemented yet (boundaries are wired, runtime integration is partial)

## Architecture

See `docs/architecture.md` for full details.

High level:

```text
Browser mic -> WS JSON events -> buffered/streaming turn processing -> VAD/STT/bridge/TTS adapters -> output events
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
- Browser Control Room: `http://127.0.0.1:8099/static/`

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
- `RALLEH_VOICE_OPENCLAW_BRIDGE_PROMPT_MAX_CHARS=12000`
- `RALLEH_VOICE_WS_MAX_EVENT_BYTES=262144`
- `RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES=262144`
- `RALLEH_VOICE_WS_MAX_BUFFERED_AUDIO_BYTES=8388608`
- `RALLEH_VOICE_WS_MAX_BUFFERED_CHUNKS=512`
- `RALLEH_VOICE_WS_AUTH_MODE=off|shared-secret|signed-token`
- `RALLEH_VOICE_WS_AUTH_TOKEN_REF=secret:ws_session_shared_secret`
- `RALLEH_VOICE_WS_AUTH_TOKEN_ENV_VAR=RALLEH_VOICE_WS_AUTH_TOKEN`
- `RALLEH_VOICE_WS_AUTH_TOKEN=<runtime token value>`
- `RALLEH_VOICE_WS_AUTH_SIGNING_KEY_REF=secret:ws_session_signing_key`
- `RALLEH_VOICE_WS_AUTH_SIGNING_KEY_ENV_VAR=RALLEH_VOICE_WS_AUTH_SIGNING_KEY`
- `RALLEH_VOICE_WS_AUTH_SIGNING_KEY=<runtime signing key value>`
- `RALLEH_VOICE_WS_AUTH_TOKEN_ISSUER=<optional issuer constraint>`
- `RALLEH_VOICE_WS_AUTH_TOKEN_AUDIENCE=<optional audience constraint>`
- `RALLEH_VOICE_WS_PROCESSING_MODE=buffered|streaming`
- `RALLEH_VOICE_WS_STREAMING_MAX_PENDING_CHUNKS=128`
- `RALLEH_VOICE_WS_RATE_LIMIT_BACKEND=memory|redis`
- `RALLEH_VOICE_WS_RATE_LIMIT_WINDOW_SECONDS=60`
- `RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_WINDOW=600`
- `RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_WINDOW=8388608`
- `RALLEH_VOICE_WS_RATE_LIMIT_REDIS_URL=redis://127.0.0.1:6379/0`
- `RALLEH_VOICE_WS_RATE_LIMIT_REDIS_KEY_PREFIX=ralleh:voice:ratelimit`
- `RALLEH_VOICE_WS_RATE_LIMIT_REDIS_TIMEOUT_MS=200`
- legacy aliases still accepted: `RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_MINUTE`, `RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_MINUTE`

Optional heavy dependencies:

```bash
pip install -e .[voice]
```

Optional Redis dependency for distributed limiter:

```bash
pip install -e .[redis]
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
Unexpected internal pipeline exceptions are surfaced as a generic `PIPELINE_FAILURE` message without leaking internal exception text.

Control Room UI behavior (current honest boundary):
- UI sends `session.hello` preferences metadata (agent/voice/mode/perf/barge/chunk/output volume) for forward compatibility; server may ignore these fields today.
- Voice profile selection and output volume are currently UX-level preferences and do not imply real TTS voice switching/playback yet.
- `audio.output.chunk` remains placeholder text output in this phase (not playable PCM stream).
- Auth token field is available in setup/debug panel but intentionally not persisted locally.

WebSocket auth/bootstrap contract:
- Server always emits initial `session.ready` with auth requirements, processing mode, and configured rate-limit metadata.
- In `RALLEH_VOICE_WS_AUTH_MODE=off` (default dev mode), audio can be sent immediately for deterministic local iteration.
- In `shared-secret` mode, client sends `session.hello` with `payload.auth_token` (or `payload.auth.token`) matching runtime env token (`RALLEH_VOICE_WS_AUTH_TOKEN` by default).
- In `signed-token` mode, client sends an HMAC token with claims: `iat`, `exp`, `sid`, `clt`, optional `iss`, optional `aud`.
- Signed token verification checks signature, expiry, iat, and configured issuer/audience constraints.
- Structured auth failures: `AUTH_MISSING_TOKEN`, `AUTH_BAD_SIGNATURE`, `AUTH_EXPIRED`, `AUTH_BAD_FORMAT`, `AUTH_INVALID_CLAIM`, `AUTH_CONFIG_ERROR`.
- While auth is required, audio events before successful hello/auth return `AUTH_REQUIRED` and are ignored.

Rate-limiting contract:
- sliding window (default 60s) for inbound event count and decoded audio bytes
- over-limit events return `session.error` code `RATE_LIMITED` with structured `meta.kind` (`events_per_window` or `audio_bytes_per_window`)
- audio-byte over-limit also clears buffered turn state and emits `session.done` with `reason=rate-limited`
- backend `memory` is default and process-local
- backend `redis` uses atomic Lua increment checks per identity and window bucket
- if redis is configured but unavailable/missing dependency, limiter degrades safely to in-memory with metadata (`degraded=true`)

Streaming processing contract:
- `buffered` mode preserves prior behavior: collect chunks until `audio.input.end`, then run turn
- `streaming` mode starts pipeline at first chunk and uses bounded queue (`RALLEH_VOICE_WS_STREAMING_MAX_PENDING_CHUNKS`)
- emits `stt.partial` before `stt.final` in deterministic mode
- `audio.input.end` remains required to finalize turn input
- cancel/barge-in keeps working in both modes
- **honest limitation:** this is lower-buffering turn-start behavior, not true full-duplex model streaming yet; adapter-level real-time streaming remains adapter-specific follow-up work

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
- WS auth secret/signing key values must be runtime-only (never committed)

## Roadmap (next slices)

1. AudioWorklet path + jitter buffering + playback improvements
2. Complete Silero/Faster-Whisper/Kokoro runtime audio wiring (beyond boundary/skeleton)
3. True adapter-level low-latency streaming (incremental STT/TTS + playback framing)
4. Tenant-aware quota policies and gateway-coordinated global throttling
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
