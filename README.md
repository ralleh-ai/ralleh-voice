# ralleh-voice

A self-hosted, browser-first voice gateway for the Ralleh / OpenClaw stack.

`ralleh-voice` provides the session layer between a browser operator UI and an agent runtime. It is built around a clean WebSocket contract, a production-minded Control Room, deterministic defaults for testability, and an adapter model that lets real VAD, STT, bridge, and TTS components be introduced without turning the service into a guessing game.

The design goal is simple:
- make browser voice sessions easy to reason about
- make deployment straightforward on a Linux VPS
- make real-model integration possible without sacrificing service safety
- make the repository honest, educational, and verifiable

## Who this repo is for

This repository is for engineers who want to run a self-hosted voice path with:
- browser microphone input
- structured WebSocket session events
- an agent bridge through OpenClaw Gateway
- optional real adapters for VAD, STT, and TTS
- explicit operational posture for Caddy, systemd, and fresh-box deployment checks

It is especially useful if you care about two things at once:
1. a clean developer/operator experience
2. honest boundaries around what is proven versus what is still in progress

## What this repo is

This repo contains:
- a FastAPI application with HTTP health/readiness endpoints and a voice WebSocket endpoint
- a browser Control Room for operating and observing sessions
- a pluggable adapter pipeline for VAD, STT, bridge, and TTS
- auth, rate limiting, session safety, and streaming-mode guardrails
- deployment artifacts for Caddy, systemd, Docker, and Compose
- repo documentation intended to meet a production-grade baseline

## What this repo is not

This repo is **not** currently:
- a PSTN/SIP telephony product
- a general-purpose media server
- a compliance/retention platform
- a claim that every optional model stack works on every host/runtime combination out of the box

Those may come later, but they are not the current claim.

## Current status

The project is a **real, usable foundation** for a self-hosted browser-first voice system.

### Proven today

Repository and deployment work now supports:
- browser microphone capture and chunked PCM upload over WebSocket
- structured client/server event contract
- deterministic test-safe adapters by default
- OpenClaw Gateway bridge integration via `POST /v1/chat/completions`
- shared-secret and signed-token auth modes
- in-memory and optional Redis rate limiting
- buffered and early-start streaming turn modes
- browser Control Room with session setup, live state, timeline, and diagnostics
- bundled smoke-check path for installed deployments

Host-level proof now exists for:
- install + systemd + Caddy-first service path on `srv1391721`
- real OpenClaw bridge
- real Faster-Whisper STT
- real Silero VAD
- full websocket turn lifecycle with real upstream reply

### Important truth

The service is farther along than a prototype, but it is not yet claiming final production perfection.

### Not fully complete yet

Remaining major work includes:
- real Kokoro host synthesis proof on the deployment target
- true speaker playback pipeline instead of placeholder fallback output when deterministic TTS is active
- true full-duplex streaming conversation behavior
- deeper production hardening, load testing, and long-run operational validation

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
# all optional voice adapters
pip install -e .[voice]

# STT only
pip install -e .[stt]

# TTS only
pip install -e .[tts]

# VAD only
pip install -e .[vad]
```

Use the narrowest extra that matches the rehearsal or deployment target. For example, Faster-Whisper host proofs should use `.[stt]` without forcing Kokoro/Torch installation.

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

Dependency audit checks:

```bash
# strict, blocking baseline for runtime + dev + redis footprint
.venv/bin/pip-audit

# optional voice baseline (direct optional packages only)
.venv/bin/pip-audit -r requirements/audit/voice-direct-baseline.txt --no-deps
```

CI treats the first check as blocking and the second as advisory so optional voice stack risk stays visible without destabilizing core verification.
The advisory voice audit also uploads a JSON artifact (`pip-audit-voice-direct`) for triage history in workflow runs.
Dependabot is enabled for both `pip` and GitHub Actions updates on a weekly cadence.

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
- `audio.output.chunk` uses placeholder text in deterministic/stub mode; when `RALLEH_VOICE_ADAPTER_TTS=kokoro`, websocket output is emitted as base64-encoded `pcm_s16le` audio chunks with sample-rate metadata.
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
- rate limiter degraded-mode diagnostics (`degraded`, `detail`) when Redis falls back to memory

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

Token helper CLI:
- `ralleh-voice-token mint ...`
- `ralleh-voice-token verify ...`

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
- `silero`: runtime wiring is implemented for CPU-first chunk detection via `silero-vad`; host proof still depends on Torch/Silero runtime availability on the deployment target
- `faster-whisper`: lazy dependency/model init boundary in place; full streaming transcription wiring still pending
- `kokoro`: runtime synthesis wiring is implemented for `pcm_s16le` output. Golden-standard safety behavior now applies: when `RALLEH_VOICE_ADAPTER_TTS=kokoro`, the service probes Kokoro at startup/readiness time; if the runtime is unavailable and `RALLEH_VOICE_KOKORO_ALLOW_FALLBACK=true` (default), deterministic TTS fallback stays active instead of breaking the service. Strict mode is still available by setting `RALLEH_VOICE_KOKORO_ALLOW_FALLBACK=false`.
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

Configuration is environment-variable driven. `.env.example` is the fastest starting point, and `ralleh_voice/config.py` remains the source of truth for defaults and validation.

This section is written for operators: each variable includes its purpose, default, accepted values or range when known, and a sample value.

### Core service

- `RALLEH_VOICE_ENV`
  - Purpose: environment label used for service context.
  - Default: `dev`
  - Example: `prod`
  - Notes: informational today, but useful for deployments and future environment-specific behavior.

- `RALLEH_VOICE_HOST`
  - Purpose: bind address for the FastAPI/uvicorn process.
  - Default: `127.0.0.1`
  - Example: `127.0.0.1`
  - Notes: keep loopback/private in production and expose via Caddy rather than binding publicly.

- `RALLEH_VOICE_PORT`
  - Purpose: TCP port for the service.
  - Default: `8099`
  - Example: `8099`
  - Range: valid TCP port integer

- `RALLEH_VOICE_LOG_LEVEL`
  - Purpose: application log verbosity.
  - Default: `info`
  - Example: `debug`
  - Notes: passed through to the app/runtime; use `info` or stricter in production unless troubleshooting.

- `RALLEH_VOICE_WS_PATH`
  - Purpose: WebSocket endpoint path.
  - Default: `/v1/ws/voice`
  - Example: `/v1/ws/voice`
  - Notes: normally leave this alone and route externally with Caddy.

- `RALLEH_VOICE_STATIC_ENABLED`
  - Purpose: enable or disable the bundled Control Room static UI.
  - Default: `true`
  - Allowed: `true|false`
  - Example: `true`

- `RALLEH_VOICE_SECURITY_HEADERS_ENABLED`
  - Purpose: enable baseline HTTP hardening headers (`nosniff`, frame deny, referrer policy, permissions policy, no-store).
  - Default: `true`
  - Allowed: `true|false`
  - Example: `true`

- `RALLEH_VOICE_CORS_ALLOW_ORIGINS`
  - Purpose: comma-separated allowlist for browser Control Room origins.
  - Default: `http://127.0.0.1,http://localhost`
  - Example: `https://voice-control.example.com`

- `RALLEH_VOICE_CORS_ALLOW_CREDENTIALS`
  - Purpose: include credentialed CORS responses when required by your browser integration.
  - Default: `false`
  - Allowed: `true|false`
  - Example: `false`
  - Notes: when set to `true`, `RALLEH_VOICE_CORS_ALLOW_ORIGINS` must be explicit (cannot include `*`).

- `RALLEH_VOICE_METRICS_ENABLED`
  - Purpose: enable Prometheus-style metrics endpoint at `/v1/metrics`.
  - Default: `false`
  - Allowed: `true|false`
  - Example: `true`

- `RALLEH_VOICE_BUILD_COMMIT`
  - Purpose: optional build metadata included in `/v1/healthz` and `/v1/readyz`.
  - Default: empty
  - Example: `a1b2c3d4`

### WebSocket limits and behavior

- `RALLEH_VOICE_WS_MAX_EVENT_BYTES`
  - Purpose: max inbound JSON event size before rejecting with `EVENT_TOO_LARGE`.
  - Default: `262144`
  - Minimum: `1`
  - Example: `262144`

- `RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES`
  - Purpose: max decoded audio chunk size accepted per `audio.input.chunk` event.
  - Default: `262144`
  - Minimum: `1`
  - Example: `65536`
  - Notes: must be less than or equal to `RALLEH_VOICE_WS_MAX_BUFFERED_AUDIO_BYTES`.

- `RALLEH_VOICE_WS_MAX_BUFFERED_AUDIO_BYTES`
  - Purpose: max per-turn buffered audio budget before overflow/reset behavior.
  - Default: `8388608`
  - Minimum: `1024`
  - Example: `8388608`

- `RALLEH_VOICE_WS_MAX_BUFFERED_CHUNKS`
  - Purpose: max number of chunks buffered for one turn.
  - Default: `512`
  - Minimum: `1`
  - Example: `512`

- `RALLEH_VOICE_WS_PROCESSING_MODE`
  - Purpose: choose turn-processing strategy.
  - Default: `buffered`
  - Allowed: `buffered|streaming`
  - Example: `streaming`
  - Notes: `streaming` is early-start/lower-buffering behavior, not true full-duplex voice yet.

- `RALLEH_VOICE_WS_STREAMING_MAX_PENDING_CHUNKS`
  - Purpose: bound queued chunks while streaming mode is active.
  - Default: `128`
  - Minimum: `1`
  - Example: `128`

### WebSocket auth

- `RALLEH_VOICE_WS_AUTH_MODE`
  - Purpose: selects the session auth mode.
  - Default: `off`
  - Allowed: `off|shared-secret|signed-token`
  - Example: `signed-token`

- `RALLEH_VOICE_WS_AUTH_TOKEN_REF`
  - Purpose: human-readable secret reference for shared-secret mode.
  - Default: `secret:ws_session_shared_secret`
  - Example: `secret:voice_ws_bootstrap`
  - Notes: metadata only; the actual secret still comes from the env var below.

- `RALLEH_VOICE_WS_AUTH_TOKEN_ENV_VAR`
  - Purpose: env var name holding the shared-secret token.
  - Default: `RALLEH_VOICE_WS_AUTH_TOKEN`
  - Example: `RALLEH_VOICE_WS_AUTH_TOKEN`

- `RALLEH_VOICE_WS_AUTH_TOKEN`
  - Purpose: actual shared-secret value used when `RALLEH_VOICE_WS_AUTH_MODE=shared-secret`.
  - Default: empty
  - Example: `change-me-32-bytes-minimum`
  - Notes: runtime secret only; never commit this.

- `RALLEH_VOICE_WS_AUTH_SIGNING_KEY_REF`
  - Purpose: human-readable secret reference for signed-token mode.
  - Default: `secret:ws_session_signing_key`
  - Example: `secret:voice_ws_hmac_signing_key`

- `RALLEH_VOICE_WS_AUTH_SIGNING_KEY_ENV_VAR`
  - Purpose: env var name holding the HMAC signing key.
  - Default: `RALLEH_VOICE_WS_AUTH_SIGNING_KEY`
  - Example: `RALLEH_VOICE_WS_AUTH_SIGNING_KEY`

- `RALLEH_VOICE_WS_AUTH_SIGNING_KEY`
  - Purpose: actual HMAC signing key used for compact signed session tokens.
  - Default: empty
  - Example: `super-long-random-signing-key`
  - Notes: required when `RALLEH_VOICE_WS_AUTH_MODE=signed-token`.

- `RALLEH_VOICE_WS_AUTH_TOKEN_TTL_SECONDS`
  - Purpose: lifetime for signed session tokens.
  - Default: `120`
  - Minimum: `1`
  - Example: `120`

- `RALLEH_VOICE_WS_AUTH_TOKEN_ISSUER`
  - Purpose: optional issuer claim required when validating signed tokens.
  - Default: empty
  - Example: `ralleh-provision`

- `RALLEH_VOICE_WS_AUTH_TOKEN_AUDIENCE`
  - Purpose: optional audience claim required when validating signed tokens.
  - Default: empty
  - Example: `ralleh-voice`

### Rate limiting

- `RALLEH_VOICE_WS_RATE_LIMIT_BACKEND`
  - Purpose: rate-limit storage backend.
  - Default: `memory`
  - Allowed: `memory|redis`
  - Example: `redis`

- `RALLEH_VOICE_WS_RATE_LIMIT_WINDOW_SECONDS`
  - Purpose: sliding/fixed limit window size in seconds.
  - Default: `60`
  - Minimum: `1`
  - Example: `60`

- `RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_WINDOW`
  - Purpose: max inbound websocket events allowed per window.
  - Default: `600`
  - Minimum: `1`
  - Example: `600`

- `RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_WINDOW`
  - Purpose: max decoded audio bytes allowed per window.
  - Default: `8388608`
  - Minimum: `1`
  - Example: `8388608`

- `RALLEH_VOICE_WS_RATE_LIMIT_INCLUDE_IP_FOR_ANONYMOUS`
  - Purpose: include client IP in anonymous limiter identity buckets as a secondary anti-abuse signal.
  - Default: `false`
  - Allowed: `true|false`
  - Example: `true`

- `RALLEH_VOICE_WS_RATE_LIMIT_REDIS_URL`
  - Purpose: Redis connection string used when backend is `redis`.
  - Default: `redis://127.0.0.1:6379/0`
  - Example: `redis://127.0.0.1:6379/0`

- `RALLEH_VOICE_WS_RATE_LIMIT_REDIS_KEY_PREFIX`
  - Purpose: key namespace prefix for Redis-backed rate limits.
  - Default: `ralleh:voice:ratelimit`
  - Example: `ralleh:voice:ratelimit`

- `RALLEH_VOICE_WS_RATE_LIMIT_REDIS_TIMEOUT_MS`
  - Purpose: Redis operation timeout.
  - Default: `200`
  - Minimum: `1`
  - Example: `200`

Legacy aliases still accepted for compatibility:
- `RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_MINUTE`
- `RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_MINUTE`

### OpenClaw bridge

- `RALLEH_VOICE_OPENCLAW_GATEWAY_URL`
  - Purpose: base URL for the local OpenClaw Gateway OpenAI-compatible endpoint.
  - Default: `http://127.0.0.1:18789`
  - Example: `http://127.0.0.1:18789`

- `RALLEH_VOICE_OPENCLAW_AGENT_TARGET`
  - Purpose: model/agent target sent to `/v1/chat/completions`.
  - Default: `openclaw/default`
  - Example: `openclaw/default`

- `RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN_ENV_VAR`
  - Purpose: env var name holding the Gateway bearer token.
  - Default: `RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN`
  - Example: `RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN`

- `RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN`
  - Purpose: actual bearer token for bridge requests.
  - Default: empty
  - Example: `replace-with-runtime-token`
  - Notes: runtime secret only; never commit this.

- `RALLEH_VOICE_OPENCLAW_GATEWAY_ALLOW_UNAUTHENTICATED`
  - Purpose: allow bridge requests without a bearer token.
  - Default: `false`
  - Allowed: `true|false`
  - Example: `false`
  - Notes: leave `false` unless you fully trust the private network path.

- `RALLEH_VOICE_OPENCLAW_SESSION_KEY_PREFIX`
  - Purpose: prefix used when generating deterministic `x-openclaw-session-key` values.
  - Default: `ralleh-voice`
  - Example: `ralleh-voice`

- `RALLEH_VOICE_OPENCLAW_GATEWAY_TIMEOUT_MS`
  - Purpose: bridge request timeout.
  - Default: `10000`
  - Minimum: `1`
  - Example: `15000`

- `RALLEH_VOICE_OPENCLAW_BRIDGE_PROMPT_MAX_CHARS`
  - Purpose: guardrail on transcript/prompt size sent upstream.
  - Default: `12000`
  - Minimum: `1`
  - Example: `12000`

### Adapter selection

- `RALLEH_VOICE_ADAPTER_VAD`
  - Purpose: choose the voice activity detector implementation.
  - Default: `deterministic`
  - Allowed: `deterministic|stub|silero`
  - Example: `silero`

- `RALLEH_VOICE_ADAPTER_STT`
  - Purpose: choose the speech-to-text implementation.
  - Default: `deterministic`
  - Allowed: `deterministic|stub|faster-whisper`
  - Example: `faster-whisper`

- `RALLEH_VOICE_ADAPTER_TTS`
  - Purpose: choose the text-to-speech implementation.
  - Default: `deterministic`
  - Allowed: `deterministic|stub|kokoro`
  - Example: `kokoro`

- `RALLEH_VOICE_ADAPTER_BRIDGE`
  - Purpose: choose the upstream agent bridge implementation.
  - Default: `deterministic`
  - Allowed: `deterministic|stub|openclaw-gateway`
  - Example: `openclaw-gateway`

### Faster-Whisper STT tuning

- `RALLEH_VOICE_FASTER_WHISPER_MODEL_REF`
  - Purpose: logical model reference label for STT configuration/observability.
  - Default: `model:faster-whisper-tiny`
  - Example: `model:faster-whisper-tiny`

- `RALLEH_VOICE_FASTER_WHISPER_DEVICE`
  - Purpose: compute target for Faster-Whisper.
  - Default: `cpu`
  - Example: `cpu`
  - Notes: keep `cpu` unless you have a real GPU-backed deployment plan.

- `RALLEH_VOICE_FASTER_WHISPER_COMPUTE_TYPE`
  - Purpose: Faster-Whisper compute precision/profile.
  - Default: `int8`
  - Example: `int8`

### Silero VAD tuning

- `RALLEH_VOICE_SILERO_MODEL_REF`
  - Purpose: logical model reference label for VAD configuration/observability.
  - Default: `model:silero-vad`
  - Example: `model:silero-vad`

- `RALLEH_VOICE_SILERO_SAMPLE_RATE`
  - Purpose: sample rate passed to Silero.
  - Default: `16000`
  - Allowed: `8000|16000`
  - Example: `16000`

- `RALLEH_VOICE_SILERO_THRESHOLD`
  - Purpose: speech detection sensitivity threshold.
  - Default: `0.5`
  - Example: `0.5`
  - Notes: lower can detect more borderline speech; higher can reduce false positives.

- `RALLEH_VOICE_SILERO_MIN_SPEECH_MS`
  - Purpose: minimum speech duration before Silero counts a region as speech.
  - Default: `250`
  - Example: `250`

- `RALLEH_VOICE_SILERO_MIN_SILENCE_MS`
  - Purpose: minimum silence duration before Silero closes a speech region.
  - Default: `150`
  - Example: `150`

### Kokoro TTS tuning

- `RALLEH_VOICE_KOKORO_MODEL_REF`
  - Purpose: logical model reference label for TTS configuration/observability.
  - Default: `model:kokoro`
  - Example: `model:kokoro`

- `RALLEH_VOICE_KOKORO_VOICE`
  - Purpose: selected Kokoro voice name.
  - Default: `af_bella`
  - Example: `af_bella`

- `RALLEH_VOICE_KOKORO_LANG_CODE`
  - Purpose: Kokoro language code used when building `KPipeline`.
  - Default: `a`
  - Example: `a`
  - Notes: `a` is the current American English path used in rehearsal/test code.

- `RALLEH_VOICE_KOKORO_SAMPLE_RATE`
  - Purpose: sample rate declared for Kokoro output events.
  - Default: `24000`
  - Example: `24000`

- `RALLEH_VOICE_KOKORO_OUTPUT_FORMAT`
  - Purpose: output encoding expected from the Kokoro adapter.
  - Default: `pcm_s16le`
  - Allowed: currently only `pcm_s16le`
  - Example: `pcm_s16le`

- `RALLEH_VOICE_KOKORO_ALLOW_FALLBACK`
  - Purpose: keep the service healthy by falling back to deterministic TTS if Kokoro probing fails.
  - Default: `true`
  - Allowed: `true|false`
  - Example: `true`
  - Notes: this is the golden-standard safety default. Set to `false` only when you want strict failure instead of graceful degradation.

### Audio input baseline

- `RALLEH_VOICE_AUDIO_SAMPLE_RATE`
  - Purpose: expected PCM input sample rate used by the audio pipeline.
  - Default: `16000`
  - Example: `16000`
  - Notes: this is the core mono speech input baseline used by the current host proofs.

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
