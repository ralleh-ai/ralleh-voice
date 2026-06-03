# ralleh-voice

Standalone voice gateway/package for the Ralleh stack.

This repo is intentionally **foundation-first**:
- clear runtime/event contracts,
- deployment + operations shape,
- provisioning integration contract,
- minimal FastAPI + WebSocket skeleton,
- adapter interfaces/stubs for VAD/STT/OpenClaw bridge/TTS.

It is designed to be:
1. optional during `ralleh-provision` install,
2. installable later as an independent app,
3. browser/mobile voice first.

> Real PSTN phone calls are a **future transport layer** (SIP/Asterisk/FreeSWITCH or GSM/LTE modem hardware), not part of this initial foundation.

## Status

This is not a production voice system yet.

Implemented now:
- HTTP health/readiness endpoints,
- static browser test client placeholder,
- WebSocket session scaffold + event envelope contract,
- adapter interfaces and no-op stubs,
- deploy artifacts (Docker, compose, Caddy, systemd, install script),
- tests for config, health payload, and event contract shape.

Deferred (documented TODOs):
- production VAD,
- Faster-Whisper integration,
- OpenClaw bridge transport,
- Kokoro streaming synthesis,
- authn/authz and tenant isolation,
- barge-in tuned behavior + audio buffering strategy.

## Repo layout

- `ralleh_voice/` – Python package
- `static/` – browser placeholder mic/WebSocket client
- `docs/` – architecture, security, ops, deploy/provisioning contracts
- `deploy/` – Docker/Caddy/systemd artifacts
- `scripts/` – installation/bootstrap helpers
- `tests/` – lightweight tests

## Quick start (local dev)

```bash
cd ralleh-voice
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
uvicorn ralleh_voice.app:app --host 127.0.0.1 --port 8099 --reload
```

Open:
- API health: `http://127.0.0.1:8099/v1/healthz`
- Browser client: `http://127.0.0.1:8099/static/`

Run tests:

```bash
pytest
```

## Configuration

Environment-variable based. See `.env.example` and `ralleh_voice/config.py`.

## Provisioning integration

See `docs/provisioning-integration.md` for optional `spec.voice` manifest shape and generated artifact/verification expectations.

## License

MIT (to be finalized with project policy if needed).
