#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import urlopen


@dataclass(slots=True)
class SmokeResult:
    ok: bool
    message: str


def ok(message: str) -> SmokeResult:
    return SmokeResult(True, message)


def fail(message: str) -> SmokeResult:
    return SmokeResult(False, message)


def print_result(result: SmokeResult) -> None:
    prefix = "[ok]" if result.ok else "[fail]"
    print(f"{prefix} {result.message}")


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as resp:
        data = resp.read().decode("utf-8")
    return json.loads(data)


def fetch_text(url: str, timeout: float) -> str:
    with urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def derive_ws_url(base_url: str, ws_path: str) -> str:
    parts = urlsplit(base_url)
    scheme = "wss" if parts.scheme == "https" else "ws"
    path = ws_path if ws_path.startswith("/") else f"/{ws_path}"
    return urlunsplit((scheme, parts.netloc, path, "", ""))


def path_url(base_url: str, path: str) -> str:
    parts = urlsplit(base_url)
    base_path = parts.path.rstrip("/")
    full_path = f"{base_path}{path}" if base_path else path
    return urlunsplit((parts.scheme, parts.netloc, full_path, "", ""))


def check_health(base_url: str, timeout: float) -> SmokeResult:
    payload = fetch_json(path_url(base_url, "/v1/healthz"), timeout)
    if payload.get("service") != "ralleh-voice":
        return fail("/v1/healthz returned unexpected service name")
    if payload.get("status") != "ok":
        return fail("/v1/healthz did not report status=ok")
    return ok(f"healthz ok · version {payload.get('version', 'unknown')}")


def check_ready(base_url: str, timeout: float, require_ready: bool) -> SmokeResult:
    payload = fetch_json(path_url(base_url, "/v1/readyz"), timeout)
    if payload.get("service") != "ralleh-voice":
        return fail("/v1/readyz returned unexpected service name")
    ready = payload.get("ready") is True
    if require_ready and not ready:
        return fail(f"readyz reported ready=false · adapters={payload.get('adapters', {})}")
    return ok(f"readyz reachable · ready={str(ready).lower()}")


def check_static(base_url: str, timeout: float) -> SmokeResult:
    html = fetch_text(path_url(base_url, "/static/"), timeout)
    required_markers = [
        "Ralleh Voice Control Room",
        "You are talking to",
        "Transcript & turn timeline",
        "Diagnostics & tuning",
    ]
    missing = [marker for marker in required_markers if marker not in html]
    if missing:
        return fail(f"static UI missing expected markers: {', '.join(missing)}")
    return ok("static Control Room served expected structure")


async def check_ws_turn(ws_url: str, timeout: float, auth_token: str | None, require_turn: bool) -> SmokeResult:
    try:
        import websockets
    except Exception as exc:  # pragma: no cover - operator environment dependent
        return fail(
            "websocket smoke check requires the 'websockets' package; install dev deps or pip install websockets"
        )

    try:
        async with websockets.connect(ws_url, open_timeout=timeout, close_timeout=timeout, max_size=2**20) as ws:
            initial = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if initial.get("type") != "session.ready":
                return fail(f"unexpected first websocket event: {initial.get('type')}")

            session_info = initial.get("payload", {}).get("session", {})
            auth_required = session_info.get("auth_required") is True
            if auth_required and not auth_token:
                return fail("websocket reports auth required but no --auth-token was provided")

            hello_payload: dict[str, Any] = {
                "client": "smoke-check",
                "protocol": "v0",
                "preferences": {
                    "agent_target": "openclaw/default",
                    "voice_profile": "neutral-clear",
                    "conversation_mode": "balanced",
                    "performance_mode": "balanced",
                    "barge_in_sensitivity": 60,
                    "chunk_ms": 240,
                    "output_volume": 100,
                    "auto_reconnect": False,
                },
            }
            if auth_token:
                hello_payload["auth_token"] = auth_token

            await asyncio.wait_for(
                ws.send(json.dumps({"type": "session.hello", "payload": hello_payload})),
                timeout=timeout,
            )
            hello_ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if hello_ack.get("type") != "session.ready":
                return fail(f"unexpected hello ack event: {hello_ack.get('type')}")

            hello_session = hello_ack.get("payload", {}).get("session", {})
            authenticated = hello_session.get("authenticated")
            if auth_required and authenticated is not True:
                return fail("session.hello did not authenticate the websocket session")

            if not require_turn:
                return ok(
                    f"websocket connected and hello acknowledged · auth_required={str(auth_required).lower()}"
                )

            pcm = base64.b64encode(b"hello world").decode("ascii")
            await asyncio.wait_for(
                ws.send(
                    json.dumps(
                        {
                            "type": "audio.input.chunk",
                            "payload": {
                                "pcm_b64": pcm,
                                "sample_rate": 16000,
                                "channels": 1,
                                "format": "pcm_s16le",
                            },
                        }
                    )
                ),
                timeout=timeout,
            )
            await asyncio.wait_for(
                ws.send(json.dumps({"type": "audio.input.end", "payload": {}})),
                timeout=timeout,
            )

            received_types: list[str] = []
            for _ in range(8):
                event = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
                event_type = event.get("type", "")
                received_types.append(event_type)
                if event_type == "session.error":
                    payload = event.get("payload", {})
                    return fail(
                        f"turn returned session.error {payload.get('code', 'UNKNOWN')} · {payload.get('detail', 'no detail')}"
                    )
                if event_type == "session.done":
                    break

            expected_buffered = ["stt.final", "agent.reply", "audio.output.chunk", "session.done"]
            expected_streaming = ["stt.partial", "stt.final", "agent.reply", "audio.output.chunk", "session.done"]
            if received_types[:4] == expected_buffered:
                return ok("websocket turn succeeded with buffered deterministic output sequence")
            if received_types[:5] == expected_streaming:
                return ok("websocket turn succeeded with streaming deterministic output sequence")
            return fail(f"unexpected turn sequence: {received_types}")
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        return fail(f"websocket smoke check failed: {exc}")


async def async_main() -> int:
    parser = argparse.ArgumentParser(description="Post-install smoke check for ralleh-voice")
    parser.add_argument("--base-url", default="http://127.0.0.1:8099", help="Base HTTP URL (default: http://127.0.0.1:8099)")
    parser.add_argument("--ws-path", default=None, help="WebSocket path override (default: derived from base URL; /voice/v1/ws/voice under /voice ingress, otherwise /v1/ws/voice)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Per-check timeout in seconds")
    parser.add_argument("--auth-token", default=None, help="Optional auth token for protected WS modes")
    parser.add_argument("--allow-not-ready", action="store_true", help="Do not fail when /v1/readyz reports ready=false")
    parser.add_argument("--hello-only", action="store_true", help="Stop after websocket hello/ack instead of sending a turn")
    args = parser.parse_args()

    checks: list[SmokeResult] = []

    try:
        checks.append(check_health(args.base_url, args.timeout))
        checks.append(check_ready(args.base_url, args.timeout, require_ready=not args.allow_not_ready))
        checks.append(check_static(args.base_url, args.timeout))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print_result(fail(f"HTTP smoke check failed: {exc}"))
        return 1

    for result in checks:
        print_result(result)
    if not all(result.ok for result in checks):
        return 1

    ws_path = args.ws_path
    if not ws_path:
        base_path = urlsplit(args.base_url).path.rstrip("/")
        ws_path = f"{base_path}/v1/ws/voice" if base_path else "/v1/ws/voice"

    ws_url = derive_ws_url(args.base_url, ws_path)
    ws_result = await check_ws_turn(
        ws_url,
        timeout=args.timeout,
        auth_token=args.auth_token,
        require_turn=not args.hello_only,
    )
    print_result(ws_result)
    if not ws_result.ok:
        return 1

    print("[ok] smoke check complete")
    return 0


def main() -> int:
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        print("[fail] interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
