## [Unreleased]

### Added
- CORTEX #409: product polish pass for the browser client with a redesigned responsive Ralleh Voice Control Room UI in `static/index.html`.
- Agent-aware setup controls (agent target selector + custom target), voice profile selector, conversation/performance modes, and barge-in sensitivity tuning.
- Audio UX instrumentation: live mic waveform meter, RMS/peak values, clipping warning states, and timeline-style transcript/reply/event feed.
- Setup/debug drawer with auth token input (in-memory only), reconnect toggle, chunk tuning, and collapsible protocol event stream.
- Client metadata/preferences attached to `session.hello` payload for forward-compatible server-side policy handling.
- LocalStorage persistence for non-secret UI preferences only (explicitly excluding auth token persistence).

- CORTEX #407: production-hardening foundation for signed tokens, distributed limiter backend, and lower-buffering streaming turn mode.
- Signed WebSocket auth mode (`RALLEH_VOICE_WS_AUTH_MODE=signed-token`) with HMAC token verification, short-lived claims, issuer/audience checks, and structured auth failures.
- Local token utility module/CLI (`python3 -m ralleh_voice.auth_tokens`) to mint/verify signed session tokens using env-var key indirection.
- Optional distributed limiter backend (`RALLEH_VOICE_WS_RATE_LIMIT_BACKEND=redis`) using atomic Redis Lua increments, with lazy dependency import and safe in-memory degradation.
- Streaming turn mode (`RALLEH_VOICE_WS_PROCESSING_MODE=streaming`) with bounded pending queue and deterministic `stt.partial` emission.
- Tests for signed token success/failure/expiry/tamper, limiter memory+redis boundaries, and streaming mode event/cancel behavior.

### Changed
- README updated to document Control Room behavior, honest output-audio limitations, and preference persistence boundaries.
- Initial/session-ready metadata now includes processing mode and rate-limit backend/window configuration.
- Rate-limit config migrated to `*_PER_WINDOW` names with compatibility aliases for legacy `*_PER_MINUTE` env vars.
- Shared-secret path preserved; auth failure codes are now more specific (`AUTH_BAD_SIGNATURE`, `AUTH_MISSING_TOKEN`, etc.).
- Security/deploy/operations docs updated to reflect signed-token and redis-backed limiter semantics, plus honest streaming limitations.

# Changelog

## [0.2.3] - 2026-06-03

### Added
- WebSocket ingress safety limits (configurable max event bytes, max decoded chunk bytes, max turn bytes, max turn chunks).
- Tests for oversized event/chunk/turn inputs and pipeline-failure redaction behavior.

### Changed
- Generic `PIPELINE_FAILURE` websocket error detail now avoids leaking internal exception messages.
- Settings loader now validates websocket limit invariants (e.g. chunk limit cannot exceed turn limit).

### Notes
- This release hardens abuse handling without changing the deterministic default adapter posture.

## [0.2.2] - 2026-06-03

### Added
- Phase 3 OpenClaw bridge contract implementation using documented local Gateway endpoint `POST /v1/chat/completions`.
- Real `OpenClawGatewayBridge.ask()` request/response path with deterministic session-key routing header and configurable agent target.
- Bridge config surface for token env indirection, unauthenticated private-ingress override, agent target, and session-key prefix.
- Structured bridge error mapping: `CONFIG_ERROR`, `AUTH_FAILED`, `TIMEOUT`, `NETWORK_ERROR`, `UNSUPPORTED_API`, `UPSTREAM_ERROR`, `CONTRACT_MISMATCH`.
- Deterministic tests for bridge success, timeout, config validation, contract mismatch, and token redaction.

### Changed
- `/v1/readyz` now reports `openclaw-gateway` bridge readiness based on actual required config (URL/agent/token policy).
- Adapter factory wiring now passes full bridge runtime config to the OpenClaw bridge implementation.
- Docs updated from Phase 2 bridge blocker to Phase 3 pinned bridge contract.

### Notes
- CI remains deterministic/fast and does not require optional voice-model dependencies.

## [0.2.1] - 2026-06-03

### Added
- Phase 2 adapter modules/factory wiring for VAD/STT/TTS/OpenClaw bridge.
- Lazy optional dependency boundaries for `silero`, `faster-whisper`, and `kokoro` adapter modes.
- Structured adapter error model and pipeline propagation (`ADAPTER_FAILURE` over websocket).
- Real-adapter config surface for Silero/Faster-Whisper/Kokoro/OpenClaw bridge settings.
- New tests for adapter selection/failures, readiness reporting, and websocket adapter failure payloads.
- Documentation for real adapter status and OpenClaw bridge endpoint blocker.

### Changed
- `/v1/readyz` now reports per-adapter readiness and may return `ready=false` when non-ready real adapters are selected.
- `_build_pipeline` now resolves adapters via factory instead of hardcoding deterministic classes.
- Added optional `voice` dependency extras for local model-backed integration work.

### Notes
- OpenClaw gateway bridge was strict skeleton (`MISSING_ENDPOINT`) in this phase.
- CI remains deterministic/fast and does not install model-heavy optional dependencies.

## [0.2.0] - 2026-06-03

### Added
- Browser MVP client with real microphone capture and chunked PCM->base64 WebSocket streaming.
- Session state UI (connect/disconnect/reconnect/listening/processing) and transcript/reply log.
- Cancel/barge-in control from browser client.
- Event parser hardening with structured `session.error` responses.
- Support for `audio.input.end` turn-finalization event.
- Deterministic local adapters and turn pipeline outputs for testability.
- Cancellation state checks across pipeline stages.
- New unit/integration tests for parsing, pipeline behavior, cancel, and WS contract.
- `SECURITY.md`, `CONTRIBUTING.md`, GitHub Actions CI workflow.

### Changed
- Health payload now reports configured adapter modes.
- Architecture/ops/security docs updated for Phase 1 behavior and constraints.
- README expanded with status, quickstart, architecture, roadmap, non-goals.

### Notes
- Real Silero/Faster-Whisper/Kokoro/OpenClaw runtime integrations remain explicit TODOs.
