# Changelog

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
