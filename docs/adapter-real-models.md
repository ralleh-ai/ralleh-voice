# Real adapter wiring (Phase 2)

Real adapters are now selectable behind config and optional dependencies.

## Selection

- `RALLEH_VOICE_ADAPTER_VAD=deterministic|stub|silero`
- `RALLEH_VOICE_ADAPTER_STT=deterministic|stub|faster-whisper`
- `RALLEH_VOICE_ADAPTER_TTS=deterministic|stub|kokoro`
- `RALLEH_VOICE_ADAPTER_BRIDGE=deterministic|stub|openclaw-gateway`

Deterministic remains default for CI safety.

## Optional dependency install

```bash
pip install -e .[voice]
```

This installs heavy optional packages; CI should continue using `.[dev]` only.

## Current implementation limits

- Silero VAD adapter: lazy optional dependency check + structured failure; full model bootstrap still TODO.
- Faster-Whisper STT adapter: lazy optional dependency/model init boundary; real incremental transcription wiring still TODO (current streaming mode is gateway-side lower-buffering turn orchestration, not adapter-level realtime decoding).
- Kokoro TTS adapter: lazy optional dependency boundary; runtime synthesis wiring still TODO.
- OpenClaw bridge adapter: real local Gateway `/v1/chat/completions` integration with structured error mapping and token-safe failures.

All failure paths return structured adapter errors surfaced to websocket clients as `session.error` with code `ADAPTER_FAILURE`.
