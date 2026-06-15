# WebSocket signed-token helper

Ralleh Voice includes a small local utility for minting/verifying short-lived WebSocket session tokens.

Console entrypoint: `ralleh-voice-token` (also available as module `ralleh_voice.auth_tokens`).

## Contract

Token format: compact `header.payload.signature` using URL-safe base64.

- header: `{"alg":"HS256","typ":"RVS1"}`
- payload required claims:
  - `iat`: issued-at epoch seconds
  - `exp`: expiry epoch seconds
  - `sid`: session identity string
  - `clt`: client label string
- payload optional claims:
  - `iss`: issuer
  - `aud`: audience

## Runtime key handling

Signing key value must come from environment variable indirection. Do not commit secret values.

Default env var name used by helper:
- `RALLEH_VOICE_WS_AUTH_SIGNING_KEY`

## CLI examples

Mint a short-lived token (2 minutes):

```bash
export RALLEH_VOICE_WS_AUTH_SIGNING_KEY='dummy-local-signing-key'
ralleh-voice-token mint \
  --session-id sess-local-1 \
  --client browser-mvp \
  --ttl 120 \
  --issuer ralleh \
  --audience voice
```

Verify token:

```bash
ralleh-voice-token verify \
  --token '<paste token>' \
  --issuer ralleh \
  --audience voice
```

## Integration notes

When `RALLEH_VOICE_WS_AUTH_MODE=signed-token`, send token in `session.hello`:

```json
{"type":"session.hello","payload":{"client":"browser-mvp","auth_token":"<token>"}}
```

The server verifies signature and claims, then emits `session.ready` with accepted claims (no secret material). On failure it returns structured auth errors and closes the socket.
