# Contributing

Thanks for contributing to `ralleh-voice`.

## Ground rules

- Follow KISS and keep scope clear.
- Do not claim behavior that is not implemented/tested.
- Keep docs aligned with real runtime behavior.
- Keep Caddy-first deployment posture.
- Do not commit secrets, model binaries, caches, or generated junk.

## Dev setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Before opening a PR

Run:

```bash
.venv/bin/python -m pytest -q
python3 -m compileall ralleh_voice tests
git diff --check
```

And verify:
- no accidental Nginx reintroduction
- no Twilio/PSTN claims beyond current scope
- docs updated for any event/protocol changes

## Commit discipline

- Keep commits focused and reviewable.
- Include tests for behavior changes.
- Keep `main` green.
