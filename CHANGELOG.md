## [Unreleased]

### Added
- CORTEX #406: authenticated WebSocket session bootstrap and in-process rate limiting hardening slice.
- WebSocket auth bootstrap config and contract (`RALLEH_VOICE_WS_AUTH_MODE=off|shared-secret`) with runtime token env-var indirection (`RALLEH_VOICE_WS_AUTH_TOKEN_ENV_VAR`) and token reference metadata (`RALLEH_VOICE_WS_AUTH_TOKEN_REF`).
- `session.hello` shared-secret authentication path with structured `AUTH_FAILED`/`AUTH_REQUIRED` handling and clean socket close on failed auth.
- Session-ready metadata now includes auth requirements and configured limiter settings (without exposing token values).
- In-process 60-second sliding-window rate limiting for inbound event count and decoded audio bytes with structured `RATE_LIMITED` errors.
- Browser client session token input and explicit websocket error logging for auth/rate-limit feedback.
- Tests covering auth disabled path, auth required missing token, bad token rejection/redaction, good token success, and both rate-limit paths.

### Changed
- WebSocket audio ingress now requires successful hello/auth when auth mode is enabled.
- Security/deploy/operations docs updated to document one-process limiter limitation and shared-secret bootstrap posture.

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
