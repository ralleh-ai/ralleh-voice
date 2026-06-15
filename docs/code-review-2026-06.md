# Ralleh Voice code + security review (2026-06)

## Scope

Reviewed core FastAPI/WebSocket session layer, auth tokens, event parsing, rate limiting, static Control Room, deployment artifacts, and operational docs.

## Findings and actions

### Critical / High

1. **WebSocket session handler auditability risk (long nested function)**
   - File: `ralleh_voice/app.py`
   - Risk: difficult security review and future bug-prone edits in deeply nested async closure structure.
   - Action: refactored into `VoiceSessionHandler` class with focused methods for hello/auth, audio handling, turn execution, cancellation, and disconnect cleanup.

2. **Version string duplication drift risk**
   - Files: `ralleh_voice/app.py`, `tests/test_health.py`
   - Risk: health payload/app metadata can diverge from package version.
   - Action: unified runtime version sourcing via `ralleh_voice.__version__` in app health/readiness and tests.

3. **Protocol parser permissiveness**
   - File: `ralleh_voice/events.py`
   - Risk: unknown top-level/payload keys can hide client mistakes or protocol smuggling attempts.
   - Action: parser now rejects unsupported top-level fields and unsupported payload fields per inbound event type.

4. **Browser/API hardening headers and CORS control**
   - Files: `ralleh_voice/app.py`, `ralleh_voice/config.py`, `.env.example`
   - Risk: weaker default browser-facing posture and unclear origin policy.
   - Action: added baseline HTTP security headers middleware and explicit CORS allowlist config (`RALLEH_VOICE_CORS_ALLOW_ORIGINS`, `RALLEH_VOICE_CORS_ALLOW_CREDENTIALS`).

### Medium

5. **Operational visibility of degraded rate limiting**
   - File: `ralleh_voice/app.py`
   - Risk: operators can miss Redis→memory fallback context during live sessions.
   - Action: initial `session.ready` now includes `rate_limits.degraded` and `rate_limits.detail` when applicable.

6. **Token helper operator ergonomics**
   - Files: `pyproject.toml`, `docs/ws-signed-token.md`
   - Risk: token CLI exists but was module-internal only and less discoverable.
   - Action: exposed console entrypoint `ralleh-voice-token` and updated docs.

7. **Static UI XSS hygiene polish**
   - File: `static/index.html`
   - Risk: use of `innerHTML` in timeline header construction (low practical risk in current usage, but avoidable pattern).
   - Action: replaced with safe DOM node + `textContent` creation.

8. **Container least-privilege baseline**
   - File: `deploy/Dockerfile`
   - Risk: running service as root in container by default.
   - Action: add dedicated non-login `appuser`, chown app tree, run as non-root.

## Test coverage added/updated

- `tests/test_event_contract.py`
  - unknown top-level field rejection
  - unknown payload field rejection
- `tests/test_ws_contract.py`
  - unknown inbound event fields -> `BAD_EVENT`
  - degraded limiter metadata surfaced in initial `session.ready`
- `tests/test_app_security.py`
  - package version reflected in health
  - default security headers present
  - security headers can be disabled
  - CORS allow-origin uses configured allowlist
- `tests/test_health.py`
  - version assertion now tied to `__version__`

## Follow-up pass updates

- Added optional Prometheus-style runtime metrics endpoint at `/v1/metrics` behind `RALLEH_VOICE_METRICS_ENABLED`.
- Added optional IP-aware anonymous limiter identity signal via `RALLEH_VOICE_WS_RATE_LIMIT_INCLUDE_IP_FOR_ANONYMOUS`.
- Added config guardrail: credentialed CORS cannot be combined with wildcard origin (`*`).
- Added optional `RALLEH_VOICE_BUILD_COMMIT` metadata surfaced in health/readiness payloads.
- Expanded tests for metrics endpoint, CORS guardrail, and anonymous identity behavior.

## Remaining recommendations

- Continue toward true adapter-level streaming (partial STT/TTS) behind current pipeline API.

## Completed after review (follow-up)

- Added CI dependency vulnerability auditing with a two-lane strategy:
  - blocking `pip-audit` for core runtime/dev/redis footprint
  - advisory optional voice direct-package baseline via `requirements/audit/voice-direct-baseline.txt` and `--no-deps`
- This keeps core-path risk gating strict while preserving visibility into optional voice stack risk without destabilizing CI on interpreter/stack-specific extras.
