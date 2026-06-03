from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .adapters import build_adapters
from .auth_tokens import AuthTokenError, verify_signed_session_token
from .config import Settings, load_settings
from .events import (
    EVENT_AGENT_REPLY,
    EVENT_AUDIO_END,
    EVENT_AUDIO_IN,
    EVENT_AUDIO_OUT_CHUNK,
    EVENT_CANCEL,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_HELLO,
    EVENT_READY,
    EVENT_TRANSCRIPT_FINAL,
    EVENT_TRANSCRIPT_PARTIAL,
    event_envelope,
    parse_client_event,
    structured_error,
)
from .pipeline import PipelineAdapterFailure, PipelineCancelled, TurnOutput, TurnState, VoicePipeline
from .rate_limits import RateLimitResult, build_rate_limiter


@dataclass(slots=True)
class SessionState:
    session_id: str
    next_seq: int = 0
    current_turn_id: int = 0
    current_turn: TurnState | None = None
    turn_task: asyncio.Task[None] | None = None
    incoming_chunks: list[bytes] = field(default_factory=list)
    incoming_bytes: int = 0
    hello_received: bool = False
    auth_ok: bool = False
    auth_mode: str = "off"
    auth_identity: str = "anonymous"
    client_label: str = "unknown"
    connected_at_ms: int = 0
    stream_queue: asyncio.Queue[bytes | None] | None = None
    stream_pending_chunks: int = 0

    def next(self) -> int:
        seq = self.next_seq
        self.next_seq += 1
        return seq


def health_payload() -> dict[str, Any]:
    cfg = load_settings()
    return {
        "service": "ralleh-voice",
        "status": "ok",
        "version": "0.3.0",
        "env": cfg.env,
        "components": {
            "vad": cfg.adapter_vad,
            "stt": cfg.adapter_stt,
            "openclaw_bridge": cfg.adapter_bridge,
            "tts": cfg.adapter_tts,
        },
    }


def readiness_payload() -> dict[str, Any]:
    cfg = load_settings()
    adapters = build_adapters(cfg)

    readiness_by_component: dict[str, dict[str, Any]] = {}
    for component, status in adapters.status.items():
        selected = status.get("selected")
        if component == "openclaw_bridge" and selected == "openclaw-gateway":
            readiness_by_component[component] = _openclaw_bridge_readiness(cfg, status)
            continue

        readiness_by_component[component] = {
            **status,
            "ready": selected in {"deterministic", "stub"},
        }

    ready = all(component.get("ready") is True for component in readiness_by_component.values())
    return {
        "service": "ralleh-voice",
        "ready": ready,
        "openclaw_gateway_url": cfg.openclaw_gateway_url,
        "adapters": readiness_by_component,
        "rate_limits": {
            "backend": cfg.ws_rate_limit_backend,
            "window_seconds": cfg.ws_rate_limit_window_seconds,
            "events_per_window": cfg.ws_rate_limit_events_per_window,
            "audio_bytes_per_window": cfg.ws_rate_limit_audio_bytes_per_window,
        },
        "note": "Readiness reports configured adapter readiness; real adapters may require optional deps/runtime model bootstrap.",
    }


def _openclaw_bridge_readiness(cfg: Settings, status: dict[str, Any]) -> dict[str, Any]:
    token_env_var = cfg.openclaw_gateway_token_env_var.strip()
    has_token = bool(token_env_var and os.getenv(token_env_var, "").strip())

    missing: list[str] = []
    if not cfg.openclaw_gateway_url.strip():
        missing.append("gateway_url")
    if not cfg.openclaw_agent_target.strip():
        missing.append("agent_target")
    if not cfg.openclaw_gateway_allow_unauthenticated and not has_token:
        missing.append("gateway_token")

    ready = not missing

    result = {
        **status,
        "ready": ready,
        "configured": ready,
        "token_ref": cfg.openclaw_token_ref,
        "token_env_var": token_env_var,
        "allow_unauthenticated": cfg.openclaw_gateway_allow_unauthenticated,
        "agent_target": cfg.openclaw_agent_target,
    }
    if not ready:
        result["missing"] = missing
        result["note"] = "OpenClaw bridge requires URL, agent target, and token (unless unauthenticated mode is enabled)."
    return result


def _build_pipeline(cfg: Settings) -> VoicePipeline:
    adapters = build_adapters(cfg)
    return VoicePipeline(
        vad=adapters.vad,
        stt=adapters.stt,
        bridge=adapters.bridge,
        tts=adapters.tts,
    )


def create_app():
    cfg = load_settings()
    app = FastAPI(title="ralleh-voice", version="0.3.0")

    if cfg.static_enabled:
        app.mount("/static", StaticFiles(directory="static", html=True), name="static")

        @app.get("/")
        def root_index():
            return FileResponse("static/index.html")

    @app.get("/v1/healthz")
    def healthz():
        return health_payload()

    @app.get("/v1/readyz")
    def readyz():
        return readiness_payload()

    @app.websocket(cfg.ws_path)
    async def voice_ws(ws: WebSocket):
        await ws.accept()

        session = SessionState(
            session_id=str(uuid.uuid4()),
            auth_mode=cfg.ws_auth_mode,
            connected_at_ms=int(time.time() * 1000),
        )
        pipeline = _build_pipeline(cfg)
        rate_limiter = build_rate_limiter(cfg)
        seq_lock = asyncio.Lock()

        async def send_event(event_type: str, payload: dict[str, Any]) -> None:
            async with seq_lock:
                await ws.send_text(json.dumps(event_envelope(event_type, session.session_id, session.next(), payload)))

        async def send_error(code: str, detail: str, *, meta: dict[str, Any] | None = None) -> None:
            await send_event(EVENT_ERROR, structured_error(code=code, detail=detail, meta=meta))

        async def finish_turn(*, turn_id: int | None, reason: str) -> None:
            payload: dict[str, Any] = {"reason": reason}
            if turn_id is not None:
                payload["turn_id"] = turn_id
            await send_event(EVENT_DONE, payload)

        async def send_rate_limit_error(kind: str, result: RateLimitResult, limit: int) -> None:
            meta: dict[str, Any] = {
                "kind": kind,
                "limit": limit,
                "observed": result.observed,
                "window_seconds": cfg.ws_rate_limit_window_seconds,
                "backend": result.backend,
            }
            if result.degraded and result.detail:
                meta["degraded"] = True
                meta["detail"] = result.detail
            await send_error("RATE_LIMITED", "Inbound rate exceeded configured limit", meta=meta)

        async def auth_fail_and_close(code: str, detail: str) -> None:
            await send_error(code, detail)
            await ws.close(code=1008)

        def _extract_auth_token_from_hello(payload: dict[str, Any]) -> str:
            token = payload.get("auth_token")
            if isinstance(token, str):
                return token.strip()
            auth = payload.get("auth")
            if isinstance(auth, dict):
                nested_token = auth.get("token")
                if isinstance(nested_token, str):
                    return nested_token.strip()
            return ""

        def _identity_key() -> str:
            if session.auth_ok:
                return session.auth_identity
            return f"anon:{session.session_id}"

        async def emit_turn_output(turn: TurnState, result: TurnOutput) -> None:
            await send_event(EVENT_TRANSCRIPT_FINAL, {"turn_id": turn.turn_id, "text": result.transcript})
            await send_event(EVENT_AGENT_REPLY, {"turn_id": turn.turn_id, "text": result.reply})
            for idx, out in enumerate(result.audio_chunks):
                await send_event(
                    EVENT_AUDIO_OUT_CHUNK,
                    {
                        "turn_id": turn.turn_id,
                        "index": idx,
                        "encoding": "base64-text-placeholder",
                        "chunk": out.decode("utf-8", errors="ignore"),
                    },
                )

        async def run_buffered_turn(chunks: list[bytes]) -> None:
            if not chunks:
                await send_error("EMPTY_TURN", "No audio chunks were buffered for this turn")
                return

            session.current_turn_id += 1
            turn = TurnState(turn_id=session.current_turn_id)
            session.current_turn = turn

            async def chunk_iter() -> AsyncIterator[bytes]:
                for chunk in chunks:
                    yield chunk

            try:
                result = await pipeline.run_turn(chunk_iter(), session_id=session.session_id, state=turn)
                await emit_turn_output(turn, result)
                await finish_turn(turn_id=turn.turn_id, reason="turn-complete")
            except PipelineCancelled:
                await finish_turn(turn_id=turn.turn_id, reason="cancelled")
            except PipelineAdapterFailure as exc:
                payload = exc.error.to_payload()
                await send_error("ADAPTER_FAILURE", payload["detail"], meta=payload)
                await finish_turn(turn_id=turn.turn_id, reason="error")
            except Exception:
                await send_error("PIPELINE_FAILURE", "Internal pipeline failure")
                await finish_turn(turn_id=turn.turn_id, reason="error")
            finally:
                session.current_turn = None
                session.turn_task = None

        async def run_streaming_turn(queue: asyncio.Queue[bytes | None]) -> None:
            session.current_turn_id += 1
            turn = TurnState(turn_id=session.current_turn_id)
            session.current_turn = turn

            async def chunk_iter() -> AsyncIterator[bytes]:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    session.stream_pending_chunks = max(0, session.stream_pending_chunks - 1)
                    yield item

            try:
                result = await pipeline.run_turn_streaming(
                    chunk_iter(),
                    session_id=session.session_id,
                    state=turn,
                    on_partial_transcript=lambda text: send_event(
                        EVENT_TRANSCRIPT_PARTIAL,
                        {"turn_id": turn.turn_id, "text": text},
                    ),
                )
                await emit_turn_output(turn, result)
                await finish_turn(turn_id=turn.turn_id, reason="turn-complete")
            except PipelineCancelled:
                await finish_turn(turn_id=turn.turn_id, reason="cancelled")
            except PipelineAdapterFailure as exc:
                payload = exc.error.to_payload()
                await send_error("ADAPTER_FAILURE", payload["detail"], meta=payload)
                await finish_turn(turn_id=turn.turn_id, reason="error")
            except Exception:
                await send_error("PIPELINE_FAILURE", "Internal pipeline failure")
                await finish_turn(turn_id=turn.turn_id, reason="error")
            finally:
                session.current_turn = None
                session.turn_task = None
                session.stream_queue = None
                session.stream_pending_chunks = 0

        await send_event(
            EVENT_READY,
            {
                "message": "connected",
                "protocol": "v0",
                "session": {
                    "session_id": session.session_id,
                    "auth_required": cfg.ws_auth_mode != "off",
                    "auth_mode": cfg.ws_auth_mode,
                    "authenticated": False,
                    "hello_required_before_audio": cfg.ws_auth_mode != "off",
                    "processing_mode": cfg.ws_processing_mode,
                    "rate_limits": {
                        "backend": rate_limiter.backend,
                        "window_seconds": cfg.ws_rate_limit_window_seconds,
                        "events_per_window": cfg.ws_rate_limit_events_per_window,
                        "audio_bytes_per_window": cfg.ws_rate_limit_audio_bytes_per_window,
                    },
                },
            },
        )

        try:
            while True:
                raw = await ws.receive_text()
                now = time.monotonic()

                event_limit = rate_limiter.allow_event(_identity_key(), now)
                if not event_limit.allowed:
                    await send_rate_limit_error(
                        "events_per_window",
                        event_limit,
                        cfg.ws_rate_limit_events_per_window,
                    )
                    continue

                if len(raw.encode("utf-8")) > cfg.ws_max_event_bytes:
                    await send_error(
                        "EVENT_TOO_LARGE",
                        "Inbound event exceeded configured max size",
                        meta={"limit_bytes": cfg.ws_max_event_bytes},
                    )
                    continue

                try:
                    parsed = parse_client_event(raw)
                except json.JSONDecodeError as exc:
                    await send_error("BAD_JSON", f"Malformed JSON: {exc.msg}")
                    continue
                except LookupError as exc:
                    await send_error("UNSUPPORTED_EVENT", str(exc))
                    continue
                except ValueError as exc:
                    await send_error("BAD_EVENT", str(exc))
                    continue

                if parsed.event_type == EVENT_HELLO:
                    payload = parsed.payload
                    client = payload.get("client")
                    session.client_label = client.strip() if isinstance(client, str) and client.strip() else "unknown"
                    session.hello_received = True

                    if cfg.ws_auth_mode == "off":
                        session.auth_ok = True
                        session.auth_identity = f"client:{session.client_label}"
                        await send_event(
                            EVENT_READY,
                            {
                                "protocol": "v0",
                                "status": "ok",
                                "session": {
                                    "session_id": session.session_id,
                                    "client": session.client_label,
                                    "auth_required": False,
                                    "authenticated": True,
                                },
                            },
                        )
                        continue

                    provided_token = _extract_auth_token_from_hello(payload)
                    if not provided_token:
                        await auth_fail_and_close("AUTH_MISSING_TOKEN", "Missing auth token in session.hello payload")
                        return

                    if cfg.ws_auth_mode == "shared-secret":
                        expected_token = os.getenv(cfg.ws_auth_token_env_var, "").strip()
                        if not secrets.compare_digest(provided_token, expected_token):
                            await auth_fail_and_close("AUTH_BAD_SIGNATURE", "Invalid session auth token")
                            return

                        session.auth_ok = True
                        session.auth_identity = f"client:{session.client_label}"
                        await send_event(
                            EVENT_READY,
                            {
                                "protocol": "v0",
                                "status": "ok",
                                "session": {
                                    "session_id": session.session_id,
                                    "client": session.client_label,
                                    "auth_required": True,
                                    "auth_mode": cfg.ws_auth_mode,
                                    "authenticated": True,
                                    "token_ref": cfg.ws_auth_token_ref,
                                },
                            },
                        )
                        continue

                    if cfg.ws_auth_mode == "signed-token":
                        signing_key = os.getenv(cfg.ws_auth_signing_key_env_var, "").strip()
                        try:
                            claims = verify_signed_session_token(
                                provided_token,
                                key=signing_key,
                                issuer=cfg.ws_auth_token_issuer.strip() or None,
                                audience=cfg.ws_auth_token_audience.strip() or None,
                            )
                        except AuthTokenError as exc:
                            code_map = {
                                "missing_token": "AUTH_MISSING_TOKEN",
                                "bad_signature": "AUTH_BAD_SIGNATURE",
                                "expired": "AUTH_EXPIRED",
                                "config_error": "AUTH_CONFIG_ERROR",
                                "bad_format": "AUTH_BAD_FORMAT",
                                "invalid_claim": "AUTH_INVALID_CLAIM",
                            }
                            await auth_fail_and_close(code_map.get(exc.reason, "AUTH_FAILED"), exc.detail)
                            return

                        if session.client_label != "unknown" and claims.clt != session.client_label:
                            await auth_fail_and_close("AUTH_INVALID_CLAIM", "Token client claim mismatch")
                            return

                        session.auth_ok = True
                        session.client_label = claims.clt
                        session.auth_identity = f"sid:{claims.sid}:clt:{claims.clt}"

                        ack_payload = {
                            "protocol": "v0",
                            "status": "ok",
                            "session": {
                                "session_id": session.session_id,
                                "client": session.client_label,
                                "auth_required": True,
                                "auth_mode": cfg.ws_auth_mode,
                                "authenticated": True,
                                "token_ref": cfg.ws_auth_signing_key_ref,
                                "claims": {
                                    "sid": claims.sid,
                                    "clt": claims.clt,
                                    "iat": claims.iat,
                                    "exp": claims.exp,
                                },
                            },
                        }
                        if claims.iss is not None:
                            ack_payload["session"]["claims"]["iss"] = claims.iss
                        if claims.aud is not None:
                            ack_payload["session"]["claims"]["aud"] = claims.aud

                        await send_event(EVENT_READY, ack_payload)
                        continue

                if parsed.event_type == EVENT_CANCEL:
                    if session.current_turn is not None:
                        session.current_turn.cancelled = True

                    had_buffered_audio = bool(session.incoming_chunks)
                    session.incoming_chunks.clear()
                    session.incoming_bytes = 0

                    if session.stream_queue is not None:
                        try:
                            session.stream_queue.put_nowait(None)
                        except asyncio.QueueFull:
                            pass

                    if session.turn_task is None and had_buffered_audio:
                        await finish_turn(turn_id=None, reason="cancelled")
                    continue

                if parsed.event_type == EVENT_AUDIO_IN:
                    if cfg.ws_auth_mode != "off":
                        if not session.hello_received:
                            await send_error("AUTH_REQUIRED", "session.hello is required before audio events")
                            continue
                        if not session.auth_ok:
                            await send_error("AUTH_REQUIRED", "Session is not authenticated")
                            continue

                    b64 = parsed.payload.get("pcm_b64")
                    if not isinstance(b64, str) or not b64.strip():
                        await send_error("BAD_AUDIO_CHUNK", "payload.pcm_b64 must be a non-empty base64 string")
                        continue
                    try:
                        chunk = base64.b64decode(b64, validate=True)
                    except binascii.Error:
                        await send_error("BAD_AUDIO_CHUNK", "payload.pcm_b64 must be valid base64")
                        continue

                    if not chunk:
                        await send_error("BAD_AUDIO_CHUNK", "decoded audio chunk was empty")
                        continue

                    if len(chunk) > cfg.ws_max_audio_chunk_bytes:
                        await send_error(
                            "AUDIO_CHUNK_TOO_LARGE",
                            "Decoded audio chunk exceeded configured max size",
                            meta={"limit_bytes": cfg.ws_max_audio_chunk_bytes},
                        )
                        continue

                    audio_limit = rate_limiter.allow_audio_bytes(_identity_key(), len(chunk), now)
                    if not audio_limit.allowed:
                        session.incoming_chunks.clear()
                        session.incoming_bytes = 0
                        await send_rate_limit_error(
                            "audio_bytes_per_window",
                            audio_limit,
                            cfg.ws_rate_limit_audio_bytes_per_window,
                        )
                        await finish_turn(turn_id=None, reason="rate-limited")
                        continue

                    if cfg.ws_processing_mode == "buffered":
                        if len(session.incoming_chunks) >= cfg.ws_max_buffered_chunks:
                            session.incoming_chunks.clear()
                            session.incoming_bytes = 0
                            await send_error(
                                "TURN_BUFFER_OVERFLOW",
                                "Too many audio chunks buffered for pending turn",
                                meta={"limit_chunks": cfg.ws_max_buffered_chunks},
                            )
                            await finish_turn(turn_id=None, reason="error")
                            continue

                        next_total = session.incoming_bytes + len(chunk)
                        if next_total > cfg.ws_max_buffered_audio_bytes:
                            session.incoming_chunks.clear()
                            session.incoming_bytes = 0
                            await send_error(
                                "TURN_BUFFER_OVERFLOW",
                                "Buffered audio exceeded configured max size",
                                meta={"limit_bytes": cfg.ws_max_buffered_audio_bytes},
                            )
                            await finish_turn(turn_id=None, reason="error")
                            continue

                        session.incoming_chunks.append(chunk)
                        session.incoming_bytes = next_total
                        continue

                    if session.stream_queue is None:
                        session.stream_queue = asyncio.Queue(maxsize=cfg.ws_streaming_max_pending_chunks)

                    if session.stream_pending_chunks >= cfg.ws_streaming_max_pending_chunks:
                        await send_error(
                            "TURN_BUFFER_OVERFLOW",
                            "Streaming queue exceeded configured max pending chunks",
                            meta={"limit_chunks": cfg.ws_streaming_max_pending_chunks},
                        )
                        await finish_turn(turn_id=None, reason="error")
                        continue

                    try:
                        session.stream_queue.put_nowait(chunk)
                        session.stream_pending_chunks += 1
                    except asyncio.QueueFull:
                        await send_error(
                            "TURN_BUFFER_OVERFLOW",
                            "Streaming queue is full",
                            meta={"limit_chunks": cfg.ws_streaming_max_pending_chunks},
                        )
                        await finish_turn(turn_id=None, reason="error")
                        continue

                    if session.turn_task is None:
                        session.turn_task = asyncio.create_task(run_streaming_turn(session.stream_queue))
                    continue

                if parsed.event_type == EVENT_AUDIO_END:
                    if cfg.ws_auth_mode != "off":
                        if not session.hello_received:
                            await send_error("AUTH_REQUIRED", "session.hello is required before audio events")
                            continue
                        if not session.auth_ok:
                            await send_error("AUTH_REQUIRED", "Session is not authenticated")
                            continue

                    if cfg.ws_processing_mode == "buffered":
                        if session.turn_task is not None:
                            await send_error("TURN_IN_PROGRESS", "A turn is already running")
                            continue
                        chunks = list(session.incoming_chunks)
                        session.incoming_chunks.clear()
                        session.incoming_bytes = 0
                        session.turn_task = asyncio.create_task(run_buffered_turn(chunks))
                        continue

                    if session.stream_queue is None:
                        await send_error("EMPTY_TURN", "No streaming audio chunks were received for this turn")
                        continue

                    try:
                        session.stream_queue.put_nowait(None)
                    except asyncio.QueueFull:
                        await send_error("TURN_BUFFER_OVERFLOW", "Failed to finalize streaming queue")
                        await finish_turn(turn_id=None, reason="error")
                    continue

        except WebSocketDisconnect:
            if session.current_turn is not None:
                session.current_turn.cancelled = True
            if session.stream_queue is not None:
                try:
                    session.stream_queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
            if session.turn_task is not None:
                session.turn_task.cancel()
            return

    return app


app = create_app()
