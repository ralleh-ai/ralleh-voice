# Architecture (Phase 2 adapter wiring)

## Scope stance

`ralleh-voice` is a standalone package/app. It is not embedded into every OpenClaw agent runtime.

It should be deployable either:
- during `ralleh-provision` (`spec.voice.enabled: true`), or
- later as an independent install.

## Target runtime flow (browser/mobile first)

1. Browser/mobile microphone captures PCM16 mono audio.
2. Client chunks audio and sends base64 PCM frames over WebSocket.
3. Voice gateway receives JSON events and buffers audio per turn.
4. On `audio.input.end`, gateway runs adapter-selected pipeline:
   - VAD adapter (deterministic default, optional silero)
   - STT adapter (deterministic default, optional faster-whisper)
   - bridge adapter (deterministic default, openclaw-gateway skeleton)
   - TTS adapter (deterministic default, optional kokoro)
5. Gateway emits transcript/reply/audio-output events and `session.done`.

```text
Browser Mic
   -> WS JSON events
      -> turn buffer
         -> VAD adapter
            -> STT adapter
               -> OpenClaw bridge adapter
                  -> TTS adapter
                     -> streamed output chunks/events -> Browser log/UI
```

## Event model

JSON event envelope shape:

```json
{
  "type": "audio.input.chunk",
  "session_id": "uuid",
  "seq": 12,
  "payload": {}
}
```

Inbound events (Phase 1):
- `session.hello`
- `audio.input.chunk`
- `audio.input.end`
- `session.cancel`

Outbound events (Phase 1):
- `session.ready`
- `stt.final`
- `agent.reply`
- `audio.output.chunk`
- `session.done`
- `session.error`

Malformed JSON or invalid envelope data returns `session.error` with structured payload:

```json
{ "code": "BAD_JSON", "detail": "Malformed JSON: ..." }
```

## Barge-in / cancellation behavior (Phase 1)

- Client sends `session.cancel` on user interruption.
- Server marks active turn cancelled if one is in progress.
- Pending buffered input is dropped.
- Server emits `session.done` with `reason=cancelled`.
- Pipeline has cancellation checks between STT/bridge/TTS stages to stop output generation.

This is foundational behavior, not full duplex production barge-in.

## Mobile/browser constraints

- Mic capture requires secure context (`https://` or localhost).
- iOS Safari requires explicit user gesture to start/resume `AudioContext`.
- ScriptProcessor fallback is used for broad compatibility in MVP; AudioWorklet upgrade is a roadmap item.
- Current output event payload is placeholder base64 text; no real audio playback pipeline yet.

## Adapter boundaries and TODOs

The code keeps adapters swappable and lightweight for local tests.

Implemented in Phase 2:
- explicit adapter modules + factory wiring
- deterministic adapters remain default
- real adapters are lazy optional imports
- missing dependency/config/model-path issues raise structured adapter errors

Current limitations:
- Silero/Faster-Whisper/Kokoro adapters are guarded boundaries and not full runtime audio implementations yet.
- OpenClaw bridge remains strict skeleton until this repo pins stable endpoint contract details.

## Future phone transport

Real phone calling requires transport not included here:
- SIP trunk + PBX (Asterisk/FreeSWITCH), or
- telephony provider media stream gateway.

That is a separate ingress/egress transport adapter feeding the same core voice pipeline.
