# Architecture (Phase 1 browser voice MVP)

## Scope stance

`ralleh-voice` is a standalone package/app. It is not embedded into every OpenClaw agent runtime.

It should be deployable either:
- during `ralleh-provision` (`spec.voice.enabled: true`), or
- later as an independent install.

## Target runtime flow (browser/mobile first)

1. Browser/mobile microphone captures PCM16 mono audio.
2. Client chunks audio and sends base64 PCM frames over WebSocket.
3. Voice gateway receives JSON events and buffers audio per turn.
4. On `audio.input.end`, gateway runs a deterministic pipeline for MVP:
   - VAD adapter (`deterministic`) filters empty chunks
   - STT adapter (`deterministic`) normalizes utf-8 placeholder transcript
   - bridge adapter (`deterministic`) returns predictable text reply
   - TTS adapter (`deterministic`) emits base64 placeholder output chunk
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

The code intentionally keeps adapters swappable and lightweight for local tests.

Planned real adapters (not downloaded/wired by default):
- Silero VAD adapter (`RALLEH_VOICE_ADAPTER_VAD=silero`)
- Faster-Whisper STT adapter (`RALLEH_VOICE_ADAPTER_STT=faster-whisper`)
- OpenClaw gateway bridge (`RALLEH_VOICE_ADAPTER_BRIDGE=openclaw-gateway`)
- Kokoro TTS streaming adapter (`RALLEH_VOICE_ADAPTER_TTS=kokoro`)

Current implementation maps all modes to deterministic local adapters until those integrations are safely added.

## Future phone transport

Real phone calling requires transport not included here:
- SIP trunk + PBX (Asterisk/FreeSWITCH), or
- telephony provider media stream gateway.

That is a separate ingress/egress transport adapter feeding the same core voice pipeline.
