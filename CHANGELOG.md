# Changelog

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
- OpenClaw gateway bridge remains strict skeleton (`MISSING_ENDPOINT`) until stable endpoint contract is pinned in-repo.
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
