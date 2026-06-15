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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
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


@dataclass(slots=True)
class RuntimeMetrics:
    ws_connections_total: int = 0
    ws_messages_in_total: int = 0
    ws_turns_started_total: int = 0
    ws_turns_completed_total: int = 0
    ws_turns_cancelled_total: int = 0
    ws_turns_failed_total: int = 0
    ws_rate_limited_total: int = 0
    ws_auth_failures_total: int = 0


_METRICS = RuntimeMetrics()


def _prometheus_metrics_payload() -> str:
    return "\n".join(
        [
            "# HELP ralleh_voice_ws_connections_total Total accepted websocket sessions.",
            "# TYPE ralleh_voice_ws_connections_total counter",
            f"ralleh_voice_ws_connections_total {_METRICS.ws_connections_total}",
            "# HELP ralleh_voice_ws_messages_in_total Total inbound websocket messages processed.",
            "# TYPE ralleh_voice_ws_messages_in_total counter",
            f"ralleh_voice_ws_messages_in_total {_METRICS.ws_messages_in_total}",
            "# HELP ralleh_voice_ws_turns_started_total Total turns started.",
            "# TYPE ralleh_voice_ws_turns_started_total counter",
            f"ralleh_voice_ws_turns_started_total {_METRICS.ws_turns_started_total}",
            "# HELP ralleh_voice_ws_turns_completed_total Total turns completed successfully.",
            "# TYPE ralleh_voice_ws_turns_completed_total counter",
            f"ralleh_voice_ws_turns_completed_total {_METRICS.ws_turns_completed_total}",
            "# HELP ralleh_voice_ws_turns_cancelled_total Total turns cancelled.",
            "# TYPE ralleh_voice_ws_turns_cancelled_total counter",
            f"ralleh_voice_ws_turns_cancelled_total {_METRICS.ws_turns_cancelled_total}",
            "# HELP ralleh_voice_ws_turns_failed_total Total turns failed due to adapter/pipeline errors.",
            "# TYPE ralleh_voice_ws_turns_failed_total counter",
            f"ralleh_voice_ws_turns_failed_total {_METRICS.ws_turns_failed_total}",
            "# HELP ralleh_voice_ws_rate_limited_total Total websocket rate-limit rejections.",
            "# TYPE ralleh_voice_ws_rate_limited_total counter",
            f"ralleh_voice_ws_rate_limited_total {_METRICS.ws_rate_limited_total}",
            "# HELP ralleh_voice_ws_auth_failures_total Total websocket auth handshake failures.",
            "# TYPE ralleh_voice_ws_auth_failures_total counter",
            f"ralleh_voice_ws_auth_failures_total {_METRICS.ws_auth_failures_total}",
            "",
        ]
    )


class VoiceSessionHandler:
    def __init__(self, ws: WebSocket, cfg: Settings):
        self.ws = ws
        self.cfg = cfg
        self.session = SessionState(
            session_id=str(uuid.uuid4()),
            auth_mode=cfg.ws_auth_mode,
            connected_at_ms=int(time.time() * 1000),
        )
        self.pipeline = _build_pipeline(cfg)
        self.rate_limiter = build_rate_limiter(cfg)
        self.seq_lock = asyncio.Lock()

    async def run(self) -> None:
        await self.ws.accept()
        _METRICS.ws_connections_total += 1
        await self.send_event(EVENT_READY, self._initial_ready_payload())

        try:
            while True:
                raw = await self.ws.receive_text()
                _METRICS.ws_messages_in_total += 1
                now = time.monotonic()
                identity = self._identity_key()

                event_limit = self.rate_limiter.allow_event(identity, now)
                if not event_limit.allowed:
                    await self.send_rate_limit_error(
                        "events_per_window",
                        event_limit,
                        self.cfg.ws_rate_limit_events_per_window,
                    )
                    continue

                if len(raw.encode("utf-8")) > self.cfg.ws_max_event_bytes:
                    await self.send_error(
                        "EVENT_TOO_LARGE",
                        "Inbound event exceeded configured max size",
                        meta={"limit_bytes": self.cfg.ws_max_event_bytes},
                    )
                    continue

                try:
                    parsed = parse_client_event(raw)
                except json.JSONDecodeError as exc:
                    await self.send_error("BAD_JSON", f"Malformed JSON: {exc.msg}")
                    continue
                except LookupError as exc:
                    await self.send_error("UNSUPPORTED_EVENT", str(exc))
                    continue
                except ValueError as exc:
                    await self.send_error("BAD_EVENT", str(exc))
                    continue

                if parsed.event_type == EVENT_HELLO:
                    handled = await self.handle_hello(parsed.payload)
                    if handled:
                        if self.ws.application_state.name != "CONNECTED":
                            return
                        continue

                if parsed.event_type == EVENT_CANCEL:
                    await self.handle_cancel()
                    continue

                if parsed.event_type == EVENT_AUDIO_IN:
                    await self.handle_audio_in(parsed.payload, now)
                    continue

                if parsed.event_type == EVENT_AUDIO_END:
                    await self.handle_audio_end()
                    continue
        except WebSocketDisconnect:
            await self.cleanup_on_disconnect()

    async def send_event(self, event_type: str, payload: dict[str, Any]) -> None:
        async with self.seq_lock:
            envelope = event_envelope(event_type, self.session.session_id, self.session.next(), payload)
            await self.ws.send_text(json.dumps(envelope))

    async def send_error(self, code: str, detail: str, *, meta: dict[str, Any] | None = None) -> None:
        await self.send_event(EVENT_ERROR, structured_error(code=code, detail=detail, meta=meta))

    async def finish_turn(self, *, turn_id: int | None, reason: str) -> None:
        payload: dict[str, Any] = {"reason": reason}
        if turn_id is not None:
            payload["turn_id"] = turn_id
        await self.send_event(EVENT_DONE, payload)

    async def send_rate_limit_error(self, kind: str, result: RateLimitResult, limit: int) -> None:
        _METRICS.ws_rate_limited_total += 1
        meta: dict[str, Any] = {
            "kind": kind,
            "limit": limit,
            "observed": result.observed,
            "window_seconds": self.cfg.ws_rate_limit_window_seconds,
            "backend": result.backend,
        }
        if result.degraded and result.detail:
            meta["degraded"] = True
            meta["detail"] = result.detail
        await self.send_error("RATE_LIMITED", "Inbound rate exceeded configured limit", meta=meta)

    async def auth_fail_and_close(self, code: str, detail: str) -> None:
        _METRICS.ws_auth_failures_total += 1
        await self.send_error(code, detail)
        await self.ws.close(code=1008)

    @staticmethod
    def extract_auth_token_from_hello(payload: dict[str, Any]) -> str:
        token = payload.get("auth_token")
        if isinstance(token, str):
            return token.strip()
        auth = payload.get("auth")
        if isinstance(auth, dict):
            nested_token = auth.get("token")
            if isinstance(nested_token, str):
                return nested_token.strip()
        return ""

    def _identity_key(self) -> str:
        if self.session.auth_ok:
            return self.session.auth_identity
        if self.cfg.ws_rate_limit_include_ip_for_anonymous:
            host = getattr(self.ws.client, "host", None)
            if isinstance(host, str) and host.strip():
                return f"anon:{host}:{self.session.session_id}"
        return f"anon:{self.session.session_id}"

    def _initial_ready_payload(self) -> dict[str, Any]:
        return {
            "message": "connected",
            "protocol": "v0",
            "session": {
                "session_id": self.session.session_id,
                "auth_required": self.cfg.ws_auth_mode != "off",
                "auth_mode": self.cfg.ws_auth_mode,
                "authenticated": False,
                "hello_required_before_audio": self.cfg.ws_auth_mode != "off",
                "processing_mode": self.cfg.ws_processing_mode,
                "rate_limits": {
                    "backend": self.rate_limiter.backend,
                    "window_seconds": self.cfg.ws_rate_limit_window_seconds,
                    "events_per_window": self.cfg.ws_rate_limit_events_per_window,
                    "audio_bytes_per_window": self.cfg.ws_rate_limit_audio_bytes_per_window,
                    "degraded": bool(getattr(self.rate_limiter, "detail", "")),
                    "detail": getattr(self.rate_limiter, "detail", None),
                },
            },
        }

    def _require_auth_for_audio(self) -> bool:
        if self.cfg.ws_auth_mode == "off":
            return True
        if not self.session.hello_received:
            return False
        return self.session.auth_ok

    async def _send_auth_required_error(self) -> None:
        if not self.session.hello_received:
            await self.send_error("AUTH_REQUIRED", "session.hello is required before audio events")
            return
        if not self.session.auth_ok:
            await self.send_error("AUTH_REQUIRED", "Session is not authenticated")

    async def handle_hello(self, payload: dict[str, Any]) -> bool:
        client = payload.get("client")
        self.session.client_label = client.strip() if isinstance(client, str) and client.strip() else "unknown"
        self.session.hello_received = True

        if self.cfg.ws_auth_mode == "off":
            self.session.auth_ok = True
            self.session.auth_identity = f"client:{self.session.client_label}"
            await self.send_event(
                EVENT_READY,
                {
                    "protocol": "v0",
                    "status": "ok",
                    "session": {
                        "session_id": self.session.session_id,
                        "client": self.session.client_label,
                        "auth_required": False,
                        "authenticated": True,
                    },
                },
            )
            return True

        provided_token = self.extract_auth_token_from_hello(payload)
        if not provided_token:
            await self.auth_fail_and_close("AUTH_MISSING_TOKEN", "Missing auth token in session.hello payload")
            return True

        if self.cfg.ws_auth_mode == "shared-secret":
            expected_token = os.getenv(self.cfg.ws_auth_token_env_var, "").strip()
            if not secrets.compare_digest(provided_token, expected_token):
                await self.auth_fail_and_close("AUTH_BAD_SIGNATURE", "Invalid session auth token")
                return True

            self.session.auth_ok = True
            self.session.auth_identity = f"client:{self.session.client_label}"
            await self.send_event(
                EVENT_READY,
                {
                    "protocol": "v0",
                    "status": "ok",
                    "session": {
                        "session_id": self.session.session_id,
                        "client": self.session.client_label,
                        "auth_required": True,
                        "auth_mode": self.cfg.ws_auth_mode,
                        "authenticated": True,
                        "token_ref": self.cfg.ws_auth_token_ref,
                    },
                },
            )
            return True

        if self.cfg.ws_auth_mode == "signed-token":
            signing_key = os.getenv(self.cfg.ws_auth_signing_key_env_var, "").strip()
            try:
                claims = verify_signed_session_token(
                    provided_token,
                    key=signing_key,
                    issuer=self.cfg.ws_auth_token_issuer.strip() or None,
                    audience=self.cfg.ws_auth_token_audience.strip() or None,
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
                await self.auth_fail_and_close(code_map.get(exc.reason, "AUTH_FAILED"), exc.detail)
                return True

            if self.session.client_label != "unknown" and claims.clt != self.session.client_label:
                await self.auth_fail_and_close("AUTH_INVALID_CLAIM", "Token client claim mismatch")
                return True

            self.session.auth_ok = True
            self.session.client_label = claims.clt
            self.session.auth_identity = f"sid:{claims.sid}:clt:{claims.clt}"

            ack_payload: dict[str, Any] = {
                "protocol": "v0",
                "status": "ok",
                "session": {
                    "session_id": self.session.session_id,
                    "client": self.session.client_label,
                    "auth_required": True,
                    "auth_mode": self.cfg.ws_auth_mode,
                    "authenticated": True,
                    "token_ref": self.cfg.ws_auth_signing_key_ref,
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

            await self.send_event(EVENT_READY, ack_payload)
            return True

        return False

    async def handle_cancel(self) -> None:
        if self.session.current_turn is not None:
            self.session.current_turn.cancelled = True

        had_buffered_audio = bool(self.session.incoming_chunks)
        self.session.incoming_chunks.clear()
        self.session.incoming_bytes = 0

        if self.session.stream_queue is not None:
            try:
                self.session.stream_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

        if self.session.turn_task is None and had_buffered_audio:
            await self.finish_turn(turn_id=None, reason="cancelled")

    async def handle_audio_in(self, payload: dict[str, Any], now: float) -> None:
        if not self._require_auth_for_audio():
            await self._send_auth_required_error()
            return

        b64 = payload.get("pcm_b64")
        if not isinstance(b64, str) or not b64.strip():
            await self.send_error("BAD_AUDIO_CHUNK", "payload.pcm_b64 must be a non-empty base64 string")
            return

        try:
            chunk = base64.b64decode(b64, validate=True)
        except binascii.Error:
            await self.send_error("BAD_AUDIO_CHUNK", "payload.pcm_b64 must be valid base64")
            return

        if not chunk:
            await self.send_error("BAD_AUDIO_CHUNK", "decoded audio chunk was empty")
            return

        if len(chunk) > self.cfg.ws_max_audio_chunk_bytes:
            await self.send_error(
                "AUDIO_CHUNK_TOO_LARGE",
                "Decoded audio chunk exceeded configured max size",
                meta={"limit_bytes": self.cfg.ws_max_audio_chunk_bytes},
            )
            return

        audio_limit = self.rate_limiter.allow_audio_bytes(self._identity_key(), len(chunk), now)
        if not audio_limit.allowed:
            self.session.incoming_chunks.clear()
            self.session.incoming_bytes = 0
            await self.send_rate_limit_error(
                "audio_bytes_per_window",
                audio_limit,
                self.cfg.ws_rate_limit_audio_bytes_per_window,
            )
            await self.finish_turn(turn_id=None, reason="rate-limited")
            return

        if self.cfg.ws_processing_mode == "buffered":
            await self._handle_buffered_audio_chunk(chunk)
            return

        await self._handle_streaming_audio_chunk(chunk)

    async def _handle_buffered_audio_chunk(self, chunk: bytes) -> None:
        if len(self.session.incoming_chunks) >= self.cfg.ws_max_buffered_chunks:
            self.session.incoming_chunks.clear()
            self.session.incoming_bytes = 0
            await self.send_error(
                "TURN_BUFFER_OVERFLOW",
                "Too many audio chunks buffered for pending turn",
                meta={"limit_chunks": self.cfg.ws_max_buffered_chunks},
            )
            await self.finish_turn(turn_id=None, reason="error")
            return

        next_total = self.session.incoming_bytes + len(chunk)
        if next_total > self.cfg.ws_max_buffered_audio_bytes:
            self.session.incoming_chunks.clear()
            self.session.incoming_bytes = 0
            await self.send_error(
                "TURN_BUFFER_OVERFLOW",
                "Buffered audio exceeded configured max size",
                meta={"limit_bytes": self.cfg.ws_max_buffered_audio_bytes},
            )
            await self.finish_turn(turn_id=None, reason="error")
            return

        self.session.incoming_chunks.append(chunk)
        self.session.incoming_bytes = next_total

    async def _handle_streaming_audio_chunk(self, chunk: bytes) -> None:
        if self.session.stream_queue is None:
            self.session.stream_queue = asyncio.Queue(maxsize=self.cfg.ws_streaming_max_pending_chunks)

        if self.session.stream_pending_chunks >= self.cfg.ws_streaming_max_pending_chunks:
            await self.send_error(
                "TURN_BUFFER_OVERFLOW",
                "Streaming queue exceeded configured max pending chunks",
                meta={"limit_chunks": self.cfg.ws_streaming_max_pending_chunks},
            )
            await self.finish_turn(turn_id=None, reason="error")
            return

        try:
            self.session.stream_queue.put_nowait(chunk)
            self.session.stream_pending_chunks += 1
        except asyncio.QueueFull:
            await self.send_error(
                "TURN_BUFFER_OVERFLOW",
                "Streaming queue is full",
                meta={"limit_chunks": self.cfg.ws_streaming_max_pending_chunks},
            )
            await self.finish_turn(turn_id=None, reason="error")
            return

        if self.session.turn_task is None and self.session.stream_queue is not None:
            self.session.turn_task = asyncio.create_task(self.run_streaming_turn(self.session.stream_queue))

    async def handle_audio_end(self) -> None:
        if not self._require_auth_for_audio():
            await self._send_auth_required_error()
            return

        if self.cfg.ws_processing_mode == "buffered":
            if self.session.turn_task is not None:
                await self.send_error("TURN_IN_PROGRESS", "A turn is already running")
                return
            chunks = list(self.session.incoming_chunks)
            self.session.incoming_chunks.clear()
            self.session.incoming_bytes = 0
            self.session.turn_task = asyncio.create_task(self.run_buffered_turn(chunks))
            return

        if self.session.stream_queue is None:
            await self.send_error("EMPTY_TURN", "No streaming audio chunks were received for this turn")
            return

        try:
            self.session.stream_queue.put_nowait(None)
        except asyncio.QueueFull:
            await self.send_error("TURN_BUFFER_OVERFLOW", "Failed to finalize streaming queue")
            await self.finish_turn(turn_id=None, reason="error")

    async def emit_turn_output(self, turn: TurnState, result: TurnOutput) -> None:
        await self.send_event(EVENT_TRANSCRIPT_FINAL, {"turn_id": turn.turn_id, "text": result.transcript})
        await self.send_event(EVENT_AGENT_REPLY, {"turn_id": turn.turn_id, "text": result.reply})
        tts_encoding = getattr(self.pipeline.tts, "event_encoding", "base64-text-placeholder")
        tts_sample_rate = getattr(self.pipeline.tts, "event_sample_rate", None)
        for idx, out in enumerate(result.audio_chunks):
            if tts_encoding != "base64-text-placeholder":
                payload: dict[str, Any] = {
                    "turn_id": turn.turn_id,
                    "index": idx,
                    "encoding": tts_encoding,
                    "chunk": base64.b64encode(out).decode("ascii"),
                }
                if tts_sample_rate is not None:
                    payload["sample_rate"] = tts_sample_rate
                await self.send_event(EVENT_AUDIO_OUT_CHUNK, payload)
                continue

            await self.send_event(
                EVENT_AUDIO_OUT_CHUNK,
                {
                    "turn_id": turn.turn_id,
                    "index": idx,
                    "encoding": "base64-text-placeholder",
                    "chunk": out.decode("utf-8", errors="ignore"),
                },
            )

    async def run_buffered_turn(self, chunks: list[bytes]) -> None:
        if not chunks:
            await self.send_error("EMPTY_TURN", "No audio chunks were buffered for this turn")
            return

        self.session.current_turn_id += 1
        _METRICS.ws_turns_started_total += 1
        turn = TurnState(turn_id=self.session.current_turn_id)
        self.session.current_turn = turn

        async def chunk_iter() -> AsyncIterator[bytes]:
            for chunk in chunks:
                yield chunk

        try:
            result = await self.pipeline.run_turn(chunk_iter(), session_id=self.session.session_id, state=turn)
            await self.emit_turn_output(turn, result)
            _METRICS.ws_turns_completed_total += 1
            await self.finish_turn(turn_id=turn.turn_id, reason="turn-complete")
        except PipelineCancelled:
            _METRICS.ws_turns_cancelled_total += 1
            await self.finish_turn(turn_id=turn.turn_id, reason="cancelled")
        except PipelineAdapterFailure as exc:
            _METRICS.ws_turns_failed_total += 1
            payload = exc.error.to_payload()
            await self.send_error("ADAPTER_FAILURE", payload["detail"], meta=payload)
            await self.finish_turn(turn_id=turn.turn_id, reason="error")
        except Exception:
            _METRICS.ws_turns_failed_total += 1
            await self.send_error("PIPELINE_FAILURE", "Internal pipeline failure")
            await self.finish_turn(turn_id=turn.turn_id, reason="error")
        finally:
            self.session.current_turn = None
            self.session.turn_task = None

    async def run_streaming_turn(self, queue: asyncio.Queue[bytes | None]) -> None:
        self.session.current_turn_id += 1
        _METRICS.ws_turns_started_total += 1
        turn = TurnState(turn_id=self.session.current_turn_id)
        self.session.current_turn = turn

        async def chunk_iter() -> AsyncIterator[bytes]:
            while True:
                item = await queue.get()
                if item is None:
                    break
                self.session.stream_pending_chunks = max(0, self.session.stream_pending_chunks - 1)
                yield item

        try:
            result = await self.pipeline.run_turn_streaming(
                chunk_iter(),
                session_id=self.session.session_id,
                state=turn,
                on_partial_transcript=lambda text: self.send_event(
                    EVENT_TRANSCRIPT_PARTIAL,
                    {"turn_id": turn.turn_id, "text": text},
                ),
            )
            await self.emit_turn_output(turn, result)
            _METRICS.ws_turns_completed_total += 1
            await self.finish_turn(turn_id=turn.turn_id, reason="turn-complete")
        except PipelineCancelled:
            _METRICS.ws_turns_cancelled_total += 1
            await self.finish_turn(turn_id=turn.turn_id, reason="cancelled")
        except PipelineAdapterFailure as exc:
            _METRICS.ws_turns_failed_total += 1
            payload = exc.error.to_payload()
            await self.send_error("ADAPTER_FAILURE", payload["detail"], meta=payload)
            await self.finish_turn(turn_id=turn.turn_id, reason="error")
        except Exception:
            _METRICS.ws_turns_failed_total += 1
            await self.send_error("PIPELINE_FAILURE", "Internal pipeline failure")
            await self.finish_turn(turn_id=turn.turn_id, reason="error")
        finally:
            self.session.current_turn = None
            self.session.turn_task = None
            self.session.stream_queue = None
            self.session.stream_pending_chunks = 0

    async def cleanup_on_disconnect(self) -> None:
        if self.session.current_turn is not None:
            self.session.current_turn.cancelled = True
        if self.session.stream_queue is not None:
            try:
                self.session.stream_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        if self.session.turn_task is not None:
            self.session.turn_task.cancel()


def health_payload() -> dict[str, Any]:
    cfg = load_settings()
    payload = {
        "service": "ralleh-voice",
        "status": "ok",
        "version": __version__,
        "env": cfg.env,
        "components": {
            "vad": cfg.adapter_vad,
            "stt": cfg.adapter_stt,
            "openclaw_bridge": cfg.adapter_bridge,
            "tts": cfg.adapter_tts,
        },
    }
    if cfg.build_commit:
        payload["build_commit"] = cfg.build_commit
    return payload


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
    payload = {
        "service": "ralleh-voice",
        "version": __version__,
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
    if cfg.build_commit:
        payload["build_commit"] = cfg.build_commit
    return payload


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


def _apply_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_security_headers(_request, call_next):
        response: Response = await call_next(_request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "microphone=(self)")
        response.headers.setdefault("Cache-Control", "no-store")
        return response


def _parse_cors_origins(raw: str) -> list[str]:
    origins = [part.strip() for part in raw.split(",") if part.strip()]
    return origins or ["http://127.0.0.1", "http://localhost"]


def create_app():
    cfg = load_settings()
    app = FastAPI(title="ralleh-voice", version=__version__)

    if cfg.security_headers_enabled:
        _apply_security_headers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_cors_origins(cfg.cors_allow_origins),
        allow_credentials=cfg.cors_allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

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

    if cfg.metrics_enabled:
        @app.get("/v1/metrics")
        def metrics():
            return Response(content=_prometheus_metrics_payload(), media_type="text/plain; version=0.0.4")

    @app.websocket(cfg.ws_path)
    async def voice_ws(ws: WebSocket):
        handler = VoiceSessionHandler(ws, cfg)
        await handler.run()

    return app


app = create_app()
