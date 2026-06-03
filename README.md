# ralleh-voice

A browser-first voice gateway for the Ralleh stack.

`ralleh-voice` provides a self-hosted voice session path between a browser client and the Ralleh / OpenClaw agent layer. The current focus is a clean WebSocket contract, a professional browser Control Room, deterministic defaults for testability, and clear boundaries for future real-model voice integration.

## What this repo is

This repo contains:
- a FastAPI application with a voice WebSocket endpoint
- a browser Control Room for operating and observing sessions
- a pluggable adapter pipeline for VAD, STT, bridge, and TTS
- auth, rate limiting, and streaming/session guardrails
- deployment artifacts for Caddy, systemd, Docker, and Compose
- repo docs intended to meet a production-grade baseline

## What this repo is not

This repo is **not** currently:
- a PSTN/SIP telephony product
- a fully wired real-model STT/TTS runtime out of the box
- a high-availability distributed media system
- a compliance/retention platform

Those may come later, but they are not the current claim.

## Current status

The project is a **strong foundation** for a self-hosted browser-first voice system.

Implemented today:
- browser microphone capture and chunked PCM upload over WebSocket
- structured client/server event contract
- deterministic test-safe adapters by default
- OpenClaw Gateway bridge integration via `POST /v1/chat/completions`
- shared-secret and signed-token auth modes
- in-memory and optional Redis rate limiting
- buffered and early-start streaming turn modes
- browser Control Room with session setup, live state, timeline, and diagnostics
- repo standards: tests, docs, security notes, deployment artifacts, changelog, contributing guide

Not fully complete yet:
- real Silero / Faster-Whisper / Kokoro end-to-end runtime proof
- true full-duplex streaming voice path
- actual speaker playback for `audio.output.chunk`
- production hardening and performance validation on fresh deployments

## Architecture at a glance

```text
Browser mic
  -> WebSocket JSON events
  -> buffered or streaming turn processing
  -> VAD / STT / bridge / TTS adapters
  -> transcript / reply / output events
```

Key design decisions:
- browser-first voice UX before telephony
- self-hosted deployment posture
- deterministic defaults so CI and local development do not depend on model downloads
- honest separation between current features and future-ready controls

See also:
- `docs/architecture.md`
- `docs/adapter-openclaw-bridge.md`
- `docs/adapter-real-models.md`
- `docs/ws-signed-token.md`

## Quickstart

### Local development

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

### Optional dependencies

Real-model / voice stack dependencies:

```bash
pip install -e .[voice]
```

The default install already includes the `websockets` package because the bundled post-install smoke checker depends on it.

Redis rate limiter dependency:

```bash
pip install -e .[redis]
```

## Developer verification

Run tests:

```bash
.venv/bin/python -m pytest -q
```

Compile sanity check:

```bash
python3 -m compileall ralleh_voice tests
```

Useful repo hygiene check:

```bash
git diff --check
```

## Post-install smoke check

After a fresh install or service restart, run the smoke checker against the deployed instance:

```bash
.venv/bin/python3 scripts/smoke_check.py --base-url http://127.0.0.1:8099
```

What it verifies:
- `/v1/healthz`
- `/v1/readyz`
- `/static/` Control Room markers
- WebSocket connection
- `session.hello` handshake
- deterministic turn flow (`stt.final` -> `agent.reply` -> `audio.output.chunk` -> `session.done`)

Useful flags:
- `--allow-not-ready` — tolerate `ready=false` when intentionally using incomplete real adapters
- `--hello-only` — stop after the WebSocket hello/ack path
- `--auth-token <token>` — required when the deployed instance uses protected WebSocket auth modes
- `--ws-path <path>` — override the derived WebSocket path when validating unusual ingress layouts

Examples:

```bash
# direct loopback service check
.venv/bin/python3 scripts/smoke_check.py --base-url http://127.0.0.1:8099

# public Caddy ingress mounted under /voice
.venv/bin/python3 scripts/smoke_check.py --base-url https://voice.example.com/voice
```

For installed deployments, prefer the app virtualenv interpreter so the smoke checker uses the packaged dependencies.
This script is intended to be the first confidence check after installation on a fresh box.
It is expected to work with the default install, without requiring a separate dev-only dependency step.

## Control Room overview

The browser Control Room is a 3-panel operator UI:

- **Left rail** — session setup and identity
- **Center stage** — live conversation and primary actions
- **Right rail** — diagnostics and advanced inspection

The UI is intentionally structure-first and branding-ready later. It is designed to answer these questions quickly:

1. Who am I talking to?
2. What is happening right now?
3. What can I do next?
4. What mode is this session in?
5. Is the system healthy?

Detailed UX spec:
- `docs/ux-control-room-spec.md`

## Control Room gold-standard inventory

This section is the explicit contract for what the current Control Room can display and manipulate.

### Operator controls available now

#### Identity / behavior
- agent target
- custom agent target
- voice profile
- conversation mode
- performance mode
- responsiveness profile
- custom chunk duration
- barge-in sensitivity

#### Session behavior
- output volume preference
- in-memory auth token input
- auto reconnect toggle
- connect
- disconnect
- start mic
- stop mic + send turn
- cancel / barge-in
- clear timeline
- mobile panel switching

#### Persisted locally
The Control Room stores only non-secret UI preferences in `localStorage`:
- agent target
- custom agent target
- voice profile
- conversation mode
- performance mode
- chunk profile
- chunk duration
- barge-in sensitivity
- output volume preference
- auto reconnect flag
- active mobile/stacked panel

#### Intentionally not persisted
- session/auth token

### Data the UI can display now

#### Header
- product name
- transport endpoint label
- high-level connection state

#### Center stage
- active state (`Disconnected`, `Connecting`, `Connected`, `Listening`, `Processing`)
- current session id
- state tone / live guidance
- agent identity summary
- current voice / mode / responsiveness summary
- auth / processing / continuity badges
- live caption / preview text
- microphone waveform
- RMS value
- peak value
- clipping status
- conversation timeline entries for system, transcript, reply, error, and session events

#### Right rail
- connection summary
- reconnect attempts
- session id and session metadata
- input level in dB
- clipping summary
- total turn latency
- first response timing
- chunks sent
- bytes sent
- processing mode
- debug/protocol stream

### What visibly updates or animates now

#### Continuous live motion
- microphone waveform while capture is active
- RMS / peak / dB / clip status while capture is active
- subtle live-state pulse for connecting / listening / processing

#### Event-driven updates
- connection state
- center-stage live state
- session metadata
- action guidance text
- timeline feed
- live caption text
- latency/resource counters
- reconnect counters
- control enabled/disabled state

### Honest boundaries

The Control Room intentionally exposes some future-facing preferences without pretending they are fully wired features.

Current honest limits:
- voice profile selection does **not** yet guarantee real backend TTS voice switching
- output volume is **not** yet controlling true playback output
- `audio.output.chunk` is currently placeholder text, not playable speaker audio
- fade-on-cancel is shown as pending
- voice preview is shown as coming soon
- current `streaming` mode is early-start / lower-buffering behavior, not true full-duplex streaming speech

## WebSocket contract

### Client -> server
- `session.hello`
- `audio.input.chunk`
- `audio.input.end`
- `session.cancel`

### Server -> client
- `session.ready`
- `stt.partial`
- `stt.final`
- `agent.reply`
- `audio.output.chunk`
- `session.done`
- `session.error`

### `session.ready` bootstrap data

The server bootstrap event can expose:
- session id
- auth required flag
- auth mode
- authenticated flag
- hello-required-before-audio flag
- processing mode
- rate-limit backend
- rate-limit window seconds
- events-per-window limit
- audio-bytes-per-window limit
- optional authenticated client label
- optional token reference metadata
- optional signed-token claims metadata

## Auth modes

Configured by `RALLEH_VOICE_WS_AUTH_MODE`:

- `off`
- `shared-secret`
- `signed-token`

### `off`
Development-friendly mode. Audio can be sent immediately after connection.

### `shared-secret`
The client sends `session.hello` with a token matching the configured runtime secret.

### `signed-token`
The client sends an HMAC-signed token with claims such as:
- `iat`
- `exp`
- `sid`
- `clt`
- optional `iss`
- optional `aud`

Verification checks signature, expiry, issued-at time, and optional issuer/audience constraints.

See:
- `docs/ws-signed-token.md`

## Processing modes

Configured by `RALLEH_VOICE_WS_PROCESSING_MODE`:

- `buffered`
- `streaming`

### `buffered`
Collect chunks until `audio.input.end`, then run the turn.

### `streaming`
Start processing from the first chunk with a bounded pending queue. In deterministic mode this emits `stt.partial` before `stt.final`.

Important limitation:
- this is **not** yet true full-duplex streaming conversation

## Rate limiting

Supported backends:
- `memory` (default)
- `redis` (optional)

Current protections include:
- event count per window
- decoded audio bytes per window
- inbound event size limits
- per-audio-chunk size limits
- buffered turn size limits
- buffered chunk count limits

Over-limit behavior is surfaced as structured `session.error` events and may terminate the active turn with a clear reason.

## Adapter model

Adapter families:
- VAD
- STT
- bridge
- TTS

Deterministic adapters remain the default so the repo is easy to test and reason about.

Supported / planned adapter values:
- `deterministic`
- `stub`
- `silero`
- `faster-whisper`
- `kokoro`
- `openclaw-gateway`

### Current real-adapter status
- `silero`: lazy dependency boundary in place; full runtime bootstrap still pending
- `faster-whisper`: lazy dependency/model init boundary in place; full streaming transcription wiring still pending
- `kokoro`: lazy dependency boundary in place; full synthesis wiring still pending
- `openclaw-gateway`: real HTTP integration implemented

## OpenClaw bridge

The bridge targets the local OpenClaw Gateway OpenAI-compatible endpoint:

- `POST /v1/chat/completions`

Behavior includes:
- optional bearer token auth
- deterministic session routing header via `x-openclaw-session-key`
- request/response contract validation
- structured upstream error mapping

See:
- `docs/adapter-openclaw-bridge.md`

## Configuration reference

Configuration is environment-variable driven. See `.env.example` and `ralleh_voice/config.py` for the source of truth.

### Core service
- `RALLEH_VOICE_ENV`
- `RALLEH_VOICE_HOST`
- `RALLEH_VOICE_PORT`
- `RALLEH_VOICE_LOG_LEVEL`
- `RALLEH_VOICE_WS_PATH`
- `RALLEH_VOICE_STATIC_ENABLED`

### WebSocket limits / behavior
- `RALLEH_VOICE_WS_MAX_EVENT_BYTES`
- `RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES`
- `RALLEH_VOICE_WS_MAX_BUFFERED_AUDIO_BYTES`
- `RALLEH_VOICE_WS_MAX_BUFFERED_CHUNKS`
- `RALLEH_VOICE_WS_PROCESSING_MODE`
- `RALLEH_VOICE_WS_STREAMING_MAX_PENDING_CHUNKS`

### WebSocket auth
- `RALLEH_VOICE_WS_AUTH_MODE`
- `RALLEH_VOICE_WS_AUTH_TOKEN_REF`
- `RALLEH_VOICE_WS_AUTH_TOKEN_ENV_VAR`
- `RALLEH_VOICE_WS_AUTH_TOKEN`
- `RALLEH_VOICE_WS_AUTH_SIGNING_KEY_REF`
- `RALLEH_VOICE_WS_AUTH_SIGNING_KEY_ENV_VAR`
- `RALLEH_VOICE_WS_AUTH_SIGNING_KEY`
- `RALLEH_VOICE_WS_AUTH_TOKEN_TTL_SECONDS`
- `RALLEH_VOICE_WS_AUTH_TOKEN_ISSUER`
- `RALLEH_VOICE_WS_AUTH_TOKEN_AUDIENCE`

### Rate limiting
- `RALLEH_VOICE_WS_RATE_LIMIT_BACKEND`
- `RALLEH_VOICE_WS_RATE_LIMIT_WINDOW_SECONDS`
- `RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_WINDOW`
- `RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_WINDOW`
- `RALLEH_VOICE_WS_RATE_LIMIT_REDIS_URL`
- `RALLEH_VOICE_WS_RATE_LIMIT_REDIS_KEY_PREFIX`
- `RALLEH_VOICE_WS_RATE_LIMIT_REDIS_TIMEOUT_MS`

Legacy aliases still accepted:
- `RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_MINUTE`
- `RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_MINUTE`

### OpenClaw bridge
- `RALLEH_VOICE_OPENCLAW_GATEWAY_URL`
- `RALLEH_VOICE_OPENCLAW_AGENT_TARGET`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN_ENV_VAR`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_ALLOW_UNAUTHENTICATED`
- `RALLEH_VOICE_OPENCLAW_SESSION_KEY_PREFIX`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_TIMEOUT_MS`
- `RALLEH_VOICE_OPENCLAW_BRIDGE_PROMPT_MAX_CHARS`

### Adapter selection
- `RALLEH_VOICE_ADAPTER_VAD=deterministic|stub|silero`
- `RALLEH_VOICE_ADAPTER_STT=deterministic|stub|faster-whisper`
- `RALLEH_VOICE_ADAPTER_TTS=deterministic|stub|kokoro`
- `RALLEH_VOICE_ADAPTER_BRIDGE=deterministic|stub|openclaw-gateway`

## Deployment posture

Preferred posture:
- Caddy-first
- app bound to loopback/private interface
- systemd or Compose for service management

Relevant artifacts:
- `deploy/caddy/ralleh-voice.caddy` (routes both `/voice/*` and `/v1/ws/voice*` for browser ingress)
- `deploy/systemd/ralleh-voice.service`
- `deploy/Dockerfile`
- `deploy/docker-compose.yml`

Deployment posture proven in rehearsal so far:
- clean installed package starts successfully
- bundled smoke check works with the default install footprint
- Caddy-fronted `/voice` ingress works for HTTP + WebSocket flow
- systemd-style service start and restart return to healthy smoke-check state

See:
- `docs/deploy-contract.md`
- `docs/operations.md`
- `docs/provisioning-integration.md`

## Security posture

Security notes live in:
- `SECURITY.md`
- `docs/security.md`

Current policy highlights:
- no secrets in git
- `.env` stays ignored
- deterministic adapters are preferred for safe testing
- auth secrets and signing keys must be runtime-only
- internal failures should surface as structured generic client errors, not raw exception leaks

## Roadmap

Near-term priorities:
1. AudioWorklet path, buffering, and playback improvements
2. Real Silero / Faster-Whisper / Kokoro runtime wiring validation
3. True adapter-level low-latency streaming improvements
4. Tenant-aware quotas and stronger upstream coordination
5. Fresh deployment validation and production hardening

## Related docs

- `docs/architecture.md`
- `docs/adapter-openclaw-bridge.md`
- `docs/adapter-real-models.md`
- `docs/deploy-contract.md`
- `docs/operations.md`
- `docs/provisioning-integration.md`
- `docs/security.md`
- `docs/ux-control-room-spec.md`
- `docs/ws-signed-token.md`

## Contributing and governance

- contribution guide: `CONTRIBUTING.md`
- changelog: `CHANGELOG.md`
- security reporting: `SECURITY.md`
- license: `LICENSE` (MIT)
