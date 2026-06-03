# OpenClaw bridge adapter status (Phase 2)

## What is implemented

- `RALLEH_VOICE_ADAPTER_BRIDGE=openclaw-gateway` now selects a dedicated bridge class.
- Bridge reads gateway URL + token reference from config.
- Bridge fails clearly with structured adapter error (`MISSING_ENDPOINT`) rather than pretending success.

## Why it is blocked

This repository does not yet pin a stable OpenClaw endpoint contract for “ask transcript, return text” over HTTP/WS.

Local OpenClaw runtime inspection confirms internal RPC methods exist, but this repo does not yet declare a stable, supported public endpoint path/method tuple for this use-case.

## Required follow-up

Pick and lock one bridge contract in this repo (endpoint, auth, request/response schema, timeout/retry policy), then implement `OpenClawGatewayBridge.ask()` accordingly.

Until then, use `RALLEH_VOICE_ADAPTER_BRIDGE=deterministic` for CI and development.
