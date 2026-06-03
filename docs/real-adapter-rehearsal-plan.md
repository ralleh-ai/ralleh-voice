# Real adapter rehearsal plan

_Date: 2026-06-03_

## Purpose

Move `ralleh-voice` from install-proven deterministic deployment to an honest, staged real-adapter proof path.

This plan deliberately separates:

1. **What is executable now**
2. **What is blocked by missing runtime wiring**
3. **What evidence is required before claiming production-readiness**

## Current truth

### Install-proven already

The packaged/systemd/Caddy-first path has been rehearsed successfully on `srv1391721`:

- install into `/opt/ralleh/ralleh-voice`
- systemd start
- loopback smoke check
- temporary local Caddy `/voice` ingress smoke check
- restart smoke check
- uninstall + cleanup verification

### Real-adapter status right now

#### Implemented enough to rehearse now
- `openclaw-gateway` bridge adapter
  - real HTTP integration exists
  - readiness/config/auth/error mapping is implemented

#### Not yet executable as true real-adapter rehearsal
- `silero`
  - repo runtime wiring is now implemented using the `silero-vad` package on a CPU-first path
  - deployment proof still depends on Torch/Silero runtime availability and host-level rehearsal
- `faster-whisper`
  - dependency/model init boundary exists
  - actual PCM transcription path intentionally raises `NOT_IMPLEMENTED`
- `kokoro`
  - dependency boundary exists
  - actual synthesis path intentionally raises `NOT_IMPLEMENTED`

## Decision

Do **not** claim a full real-adapter rehearsal yet.

Instead, run the work in three stages:

1. **Stage A — bridge-only real upstream rehearsal**
2. **Stage B — runtime wiring implementation for STT/TTS/VAD**
3. **Stage C — full end-to-end real-adapter rehearsal on host**

---

## Stage A — bridge-only real upstream rehearsal (do now)

### Goal

Prove that `ralleh-voice` can run with the real `openclaw-gateway` bridge on `srv1391721`, while keeping VAD/STT/TTS deterministic.

### Why this matters

This isolates the only currently implemented real adapter and proves:

- gateway auth/token path
- `/v1/chat/completions` contract
- session routing header behavior
- non-deterministic upstream reply flow
- signed-token/bootstrap expectations if enabled

### Target config

Recommended rehearsal config:

```env
RALLEH_VOICE_ADAPTER_VAD=deterministic
RALLEH_VOICE_ADAPTER_STT=deterministic
RALLEH_VOICE_ADAPTER_TTS=deterministic
RALLEH_VOICE_ADAPTER_BRIDGE=openclaw-gateway

RALLEH_VOICE_OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
RALLEH_VOICE_OPENCLAW_AGENT_TARGET=openclaw/default
RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN_ENV_VAR=RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN
RALLEH_VOICE_OPENCLAW_GATEWAY_ALLOW_UNAUTHENTICATED=false
```

Optional hardening during rehearsal:

```env
RALLEH_VOICE_WS_AUTH_MODE=signed-token
RALLEH_VOICE_WS_RATE_LIMIT_BACKEND=memory
RALLEH_VOICE_WS_PROCESSING_MODE=streaming
```

### Required evidence

- `GET /v1/readyz` reports bridge selected and ready
- smoke/hello path succeeds with installed venv interpreter
- at least one real turn returns a non-deterministic upstream `agent.reply`
- auth failures are structured when token is intentionally wrong/missing
- no token leakage in logs or client-visible error payloads

### Pass criteria

- service stays healthy
- bridge request succeeds against local OpenClaw gateway
- known-bad auth/network scenarios map to structured `ADAPTER_FAILURE`
- no raw traceback or secret leakage

---

## Stage B — runtime wiring required before full rehearsal

A full real-adapter rehearsal is blocked until the following implementation work exists.

### 1. Silero VAD runtime wiring

Need:

- explicit model bootstrap/loading path
- deterministic local model location contract
- supported CPU path on Ubuntu 24.04 / Python 3.13 host
- honest readiness behavior for loaded vs unloaded model state
- at least one host-level proof test using real PCM input

Definition of done:

- `RALLEH_VOICE_ADAPTER_VAD=silero` no longer returns `NOT_IMPLEMENTED`; it now performs real Silero chunk detection when runtime deps are present
- real speech/no-speech decision path works on sample audio

### 2. Faster-Whisper STT runtime wiring

Need:

- real PCM16 mono input path to transcription
- local model bootstrap contract
- device/compute-type behavior documented for CPU-first VPS path
- bounded latency expectations for short prompts
- sample-audio proof test with expected transcript tolerance

Definition of done:

- `RALLEH_VOICE_ADAPTER_STT=faster-whisper` no longer returns `NOT_IMPLEMENTED`
- sample utterance yields acceptable transcript output

### 3. Kokoro TTS runtime wiring

Need:

- actual synthesis implementation
- output chunk contract pinned for browser playback expectations
- sample rate/output format proof
- sample text -> audio artifact test

Definition of done:

- `RALLEH_VOICE_ADAPTER_TTS=kokoro` no longer returns `NOT_IMPLEMENTED`
- returned audio chunks are real and inspectable, not placeholder text

### 4. Adapter-level streaming truth

Need:

- honest distinction between current orchestration-level streaming and true adapter-level realtime behavior
- partial-transcript timing evidence
- interruption/barge-in behavior re-verified with real adapters

Definition of done:

- README/docs accurately describe real streaming behavior
- measured timings are captured from a host run, not guessed

---

## Stage C — full end-to-end real-adapter rehearsal (after wiring)

### Goal

Run one clean hosted rehearsal on `srv1391721` with:

- `silero` VAD
- `faster-whisper` STT
- `kokoro` TTS
- `openclaw-gateway` bridge
- signed-token auth
- streaming mode
- Caddy `/voice` ingress

### Rehearsal posture

- app bound to loopback only
- Caddy as ingress
- systemd-managed service
- runtime secrets via env file only
- no model downloads during the timed rehearsal itself if avoidable; preload/bootstrap first

### Evidence to capture

#### Host/env evidence
- CPU/RAM/disk snapshot before run
- installed package versions
- model paths used
- env knobs used (redacted where secret)

#### Service evidence
- `systemctl status ralleh-voice`
- `curl -fsS http://127.0.0.1:8099/v1/healthz`
- `curl -fsS http://127.0.0.1:8099/v1/readyz`
- Caddy validation and local `/voice` route success

#### Functional evidence
- signed-token hello succeeds
- invalid/expired token fails cleanly
- one short speech sample completes full pipeline
- transcript quality is acceptable for known sample text
- audio output is real synthesis output
- OpenClaw bridge returns real upstream reply
- cancel/barge-in path still behaves sanely

Default canonical speech-test phrase for host rehearsals:
- `Ralleh Voice system check: secure bridge connected, speech recognition active, and response pipeline ready.`

#### Performance evidence
- handshake latency
- first partial transcript latency
- final transcript latency
- bridge reply latency
- first audio chunk latency
- total turn latency

#### Failure-path evidence
- bridge token missing/invalid
- Redis unavailable when configured
- missing model path / bad model ref
- oversized audio event rejection

### Full-rehearsal pass criteria

Minimum bar:

- no `NOT_IMPLEMENTED` adapters in selected path
- one complete real voice turn succeeds end-to-end
- known failure cases are structured and safe
- restart preserves healthy readiness
- no secret leakage
- documented latency is measured, not guessed

---

## Recommended next sequence

### Immediate next best move

Run **Stage A** first.

Reason:
- it is executable now
- it validates the real OpenClaw dependency boundary
- it reduces uncertainty before spending time wiring Silero/Faster-Whisper/Kokoro

### After Stage A

Prioritize implementation in this order:

1. Faster-Whisper STT
2. Kokoro TTS
3. Silero VAD

Reasoning:
- STT and TTS are the biggest user-visible proof gap
- current deterministic VAD is enough to keep a controlled rehearsal moving until real VAD is wired
- full speech/no-speech VAD fidelity matters, but it is not the first blocker to getting a real voice turn across the line

---

## Honest status language to preserve

Use this wording unless the facts materially improve:

- `ralleh-voice` is install-proven for the deterministic/systemd/Caddy-first deployment path on `srv1391721`.
- The real OpenClaw bridge can be rehearsed next.
- Full real-adapter rehearsal is no longer blocked on repo wiring: Faster-Whisper host proof passed, Kokoro runtime synthesis is wired in-repo for `pcm_s16le` websocket output, and Silero runtime wiring is now implemented on a CPU-first path. Remaining blockers are host-level proof for Kokoro/Silero on the deployment target plus matching the Kokoro package range to the host Python version (Python 3.13 requires the relaxed `kokoro>=0.7.16,<1.0` range).

---

## Follow-up task suggestions

1. `ralleh-voice`: bridge-only real upstream rehearsal on srv1391721
2. `ralleh-voice`: implement Faster-Whisper real PCM transcription path
3. `ralleh-voice`: implement Kokoro synthesis path and real audio chunk contract
4. `ralleh-voice`: implement Silero bootstrap/runtime path
5. `ralleh-voice`: full real-adapter host rehearsal with signed-token + streaming + Caddy ingress
