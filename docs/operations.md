# Operations runbook (Phase 3)

## Process model

Single API service:
- FastAPI app with HTTP + WebSocket endpoints
- static browser MVP client (`/static`)

## Health checks

- `GET /v1/healthz` => liveness + selected adapter modes
- `GET /v1/readyz` => process/config readiness + per-adapter readiness flags
- In `openclaw-gateway` bridge mode, readiness is true only when bridge URL + agent target + token policy are satisfied.
- Post-install operator check: `.venv/bin/python3 scripts/smoke_check.py --base-url http://127.0.0.1:8099`
  - validates healthz, readyz, static Control Room, WebSocket hello path, and deterministic turn flow
  - expected to work with the default install footprint; no extra dev-only smoke-check dependency step should be required
  - for installed deployments, prefer the app virtualenv interpreter so the smoke checker uses packaged dependencies
  - when validating through public Caddy ingress under `/voice`, use `.venv/bin/python3 scripts/smoke_check.py --base-url https://voice.example.com/voice`
  - use `--hello-only` or `--allow-not-ready` when intentionally validating partial/incomplete real-adapter installs

## Logging

Current baseline: stdout logs + WebSocket event-level errors.

## Install and rehearsal lessons (do not repeat these)

These were discovered during real host rehearsals on `srv1391721` and should be treated as operator rules, not suggestions.

- **Use the app virtualenv for smoke checks.**
  - Correct pattern: `/opt/ralleh/ralleh-voice/.venv/bin/python3 /opt/ralleh/ralleh-voice/scripts/smoke_check.py ...`
  - Do not assume system `python3` has the packaged dependencies.

- **Treat `/opt/ralleh/ralleh-voice` as a deployed app tree, not a git checkout.**
  - Update flows should sync/copy source into place, then reinstall.
  - Do not tell operators to `git pull` inside `APP_ROOT` unless the deployment method explicitly created a repo there.

- **Sync the latest source tree before using new extras or editable installs.**
  - If `pyproject.toml` changed, the installed tree may not know about new extras yet.
  - Copy source first, then run `pip install -e .[...]` from the deployed tree.

- **Do not assume `rsync` is installed on fresh VPS targets.**
  - Prefer base-system-safe copy methods (`tar | tar`, shell, python) or declare `rsync` as an explicit prerequisite.

- **For staged real-adapter proofs, smoke-check in partial mode first.**
  - Use `--allow-not-ready` and/or `--hello-only` when validating staged runtime prep.
  - Then run a separate websocket proof for the actual audio-turn evidence.

- **Use a short known-good speech fixture for STT/VAD proofs.**
  - Do not start with long media files, arbitrary offsets, or ambient tracks.
  - A short clip with confirmed speech dramatically shortens diagnosis time.

- **Do not treat Kokoro as install-safe on Python 3.13 unless it has been explicitly re-proven on that target.**
  - Safe default: rely on the startup probe and deterministic fallback behavior.
  - Strict Kokoro mode should be an intentional decision, not the default assumption.

Recommended production posture:
- run behind Caddy,
- terminate TLS at edge,
- keep service loopback-bound,
- expose only reverse-proxy endpoint.

Service-management verification now proven in rehearsal:
- systemd unit shape validates when installed paths/env file exist
- service-style start reaches healthy state on loopback
- restart returns to healthy state cleanly
- post-restart smoke check succeeds

## Failure handling

- malformed JSON => `session.error` (`BAD_JSON`)
- invalid event envelope => `session.error` (`BAD_EVENT`)
- unsupported inbound type => `session.error` (`UNSUPPORTED_EVENT`)
- oversized websocket event => `session.error` (`EVENT_TOO_LARGE`)
- invalid/empty audio chunk => `session.error` (`BAD_AUDIO_CHUNK`)
- oversized decoded audio chunk => `session.error` (`AUDIO_CHUNK_TOO_LARGE`)
- per-turn chunk/byte limit exceeded => `session.error` (`TURN_BUFFER_OVERFLOW`) and turn buffer reset
- missing/failed auth in protected modes => `session.error` (`AUTH_REQUIRED`, `AUTH_MISSING_TOKEN`, `AUTH_BAD_SIGNATURE`, `AUTH_EXPIRED`, `AUTH_BAD_FORMAT`, `AUTH_INVALID_CLAIM`, `AUTH_CONFIG_ERROR`)
- rate-limit breach (events/audio bytes) => `session.error` (`RATE_LIMITED`) with structured `meta.kind` (`events_per_window` / `audio_bytes_per_window`)
- end-turn without chunks => `session.error` (`EMPTY_TURN`)
- adapter failure (missing dep/model/endpoint/auth/network/timeout/contract mismatch) => `session.error` (`ADAPTER_FAILURE`) with structured `meta`
- unexpected internal exception => `session.error` (`PIPELINE_FAILURE`) with generic detail
- cancel while a turn is active => `session.done` with `reason=cancelled`
- cancel with buffered-but-not-started audio => `session.done` with `reason=cancelled`

## Practical SLO starter targets

- health/readiness endpoint success > 99.9%
- median WS handshake < 250ms on LAN/VPS
- turn completion under 2.5s for short prompts after real model adapters are integrated

## Known MVP limitations

- deterministic adapters by default (real adapter modes are optional and may report not-ready)
- if Kokoro TTS is selected but runtime probing fails, deterministic fallback can remain active when `RALLEH_VOICE_KOKORO_ALLOW_FALLBACK=true` (default); readiness will report the degraded/fallback state explicitly
- output "audio" is placeholder base64 text chunk unless a real TTS adapter is active and healthy
- shared-secret mode is static bootstrap; signed-token mode is short-lived but key rotation flow is still manual
- redis limiter uses fixed-window counters (not full burst-friendly token-bucket shaping)
- streaming mode lowers buffering/start latency but is not full-duplex model-level realtime streaming yet
- no persistent transcript storage (intentionally minimal)
