# Architecture (foundation v0)

## Scope stance

`ralleh-voice` is a standalone package/app. It is not embedded into every OpenClaw agent runtime.

It should be deployable either:
- during `ralleh-provision` (`spec.voice.enabled: true`), or
- later as an independent install.

## Target runtime flow (browser/mobile first)

1. Browser/mobile microphone captures audio chunks.
2. Client sends chunks over WebSocket to `ralleh-voice`.
3. Voice gateway runs VAD segmentation (adapter).
4. Segmented speech routed to STT (Faster-Whisper adapter).
5. Transcript turns sent through OpenClaw bridge.
6. OpenClaw text reply sent to TTS (Kokoro adapter).
7. TTS audio streamed back to client.

```text
Browser Mic
   -> WS
      -> VAD
         -> STT (Faster-Whisper)
            -> OpenClaw bridge
               -> TTS (Kokoro)
                  -> streamed audio chunks -> Browser playback
```

## Event model

JSON event envelopes:

```json
{
  "type": "audio.input.chunk",
  "session_id": "uuid",
  "seq": 12,
  "payload": {}
}
```

Core event families (documented contract; many still TODO):
- session: `session.hello`, `session.ready`, `session.cancel`, `session.done`, `session.error`
- input: `audio.input.chunk`, future `audio.input.end`
- transcript: `stt.partial`, `stt.final`
- agent: `agent.reply`
- output: `audio.output.chunk`, future `audio.output.end`

## Barge-in / cancellation flow (target behavior)

- Client sends `session.cancel` when user interrupts.
- Gateway marks current turn cancelled.
- Gateway stops outgoing TTS stream.
- Pending OpenClaw request should be cancelled when bridge supports cancellable sessions.
- New incoming audio starts a fresh turn sequence.

In this foundation build, cancel emits `session.done` with `reason=cancelled`; full cooperative cancellation is TODO.

## Mobile/browser constraints

- Browsers often gate mic/audio behind secure contexts (`https://` or localhost).
- iOS Safari has stricter autoplay/AudioContext resume constraints.
- Large binary WS frames can stall under poor mobile networks.
- Foundation keeps event contract text-first until binary framing and codec policy are finalized.

## Future phone transport

Real phone calling requires transport not included here:
- SIP trunk + PBX (Asterisk/FreeSWITCH), or
- telephony provider media stream gateway.

That becomes a separate ingress/egress transport adapter feeding the same core voice pipeline.
