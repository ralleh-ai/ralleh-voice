# OpenClaw bridge adapter status (Phase 3)

## Pinned contract (implemented)

`ralleh-voice` now pins a concrete local OpenClaw bridge contract based on local OpenClaw docs + dist inspection:

- Endpoint: `POST /v1/chat/completions`
- Base URL: `RALLEH_VOICE_OPENCLAW_GATEWAY_URL` (default `http://127.0.0.1:18789`)
- Auth: Gateway bearer token (`Authorization: Bearer ...`) unless explicitly running trusted private ingress with unauthenticated mode enabled
- Session routing: `x-openclaw-session-key` header
- Model/agent target: OpenClaw agent-style model id (`openclaw/default` by default)

Why this contract:
- OpenClaw docs explicitly describe `/v1/chat/completions` as a stable, Gateway-exposed HTTP surface that executes normal agent runs.
- It is public/documented and does not require guessing internal RPC method names.

## Request and response shape

Request body:

```json
{
  "model": "openclaw/default",
  "messages": [{ "role": "user", "content": "<transcript text>" }]
}
```

Expected response shape (OpenAI-compatible):
- `choices[0].message.content` as assistant text

If the gateway returns an incompatible payload shape, adapter returns `CONTRACT_MISMATCH`.

## Config surface

- `RALLEH_VOICE_ADAPTER_BRIDGE=openclaw-gateway`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_URL`
- `RALLEH_VOICE_OPENCLAW_AGENT_TARGET`
- `RALLEH_VOICE_OPENCLAW_TOKEN_REF` (metadata only)
- `RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN_ENV_VAR`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_ALLOW_UNAUTHENTICATED`
- `RALLEH_VOICE_OPENCLAW_SESSION_KEY_PREFIX`
- `RALLEH_VOICE_OPENCLAW_GATEWAY_TIMEOUT_MS`

## Structured error mapping

The adapter emits structured `AdapterError` codes:

- `CONFIG_ERROR` (missing required bridge settings/token)
- `AUTH_FAILED` (HTTP 401/403)
- `TIMEOUT` (request timeout)
- `NETWORK_ERROR` (gateway unreachable)
- `UNSUPPORTED_API` (chat completions endpoint unavailable/disabled)
- `UPSTREAM_ERROR` (other non-success HTTP status)
- `CONTRACT_MISMATCH` (unexpected response schema)

Token values are never included in payload detail/meta.

## Readiness behavior

`GET /v1/readyz` now reports openclaw bridge readiness honestly for `openclaw-gateway` mode:
- URL present
- agent target present
- token present unless unauthenticated mode is explicitly allowed

When missing, readiness includes a `missing` list and `ready=false`.

## Runtime behavior

When bridge mode is selected and OpenClaw is unavailable/misconfigured, websocket turns return:
- `session.error` with `code="ADAPTER_FAILURE"`
- nested structured bridge meta with one of the codes above
- `session.done` with `reason="error"`
