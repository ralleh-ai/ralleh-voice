from __future__ import annotations

import asyncio
import base64
import binascii
import json
import uuid
from dataclasses import dataclass, field
import os
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
    event_envelope,
    parse_client_event,
    structured_error,
)
from .adapters import build_adapters
from .pipeline import PipelineAdapterFailure, PipelineCancelled, TurnState, VoicePipeline


@dataclass(slots=True)
class SessionState:
    session_id: str
    next_seq: int = 0
    current_turn_id: int = 0
    current_turn: TurnState | None = None
    turn_task: asyncio.Task[None] | None = None
    incoming_chunks: list[bytes] = field(default_factory=list)
    incoming_bytes: int = 0

    def next(self) -> int:
        seq = self.next_seq
        self.next_seq += 1
        return seq


def health_payload() -> dict[str, Any]:
    cfg = load_settings()
    return {
        "service": "ralleh-voice",
        "status": "ok",
        "version": "0.2.3",
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
    app = FastAPI(title="ralleh-voice", version="0.2.3")

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

        session = SessionState(session_id=str(uuid.uuid4()))
        pipeline = _build_pipeline(cfg)

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

        async def run_buffered_turn(chunks: list[bytes]) -> None:
            if not chunks:
                await send_error("EMPTY_TURN", "No audio chunks were buffered for this turn")
                return

            session.current_turn_id += 1
            turn = TurnState(turn_id=session.current_turn_id)
            session.current_turn = turn

            async def chunk_iter():
                for chunk in chunks:
                    yield chunk

            try:
                result = await pipeline.run_turn(chunk_iter(), session_id=session.session_id, state=turn)
                await send_event(EVENT_TRANSCRIPT_FINAL, {"turn_id": turn.turn_id, "text": result.transcript})
                await send_event(EVENT_AGENT_REPLY, {"turn_id": turn.turn_id, "text": result.reply})
                for i, out in enumerate(result.audio_chunks):
                    await send_event(
                        EVENT_AUDIO_OUT_CHUNK,
                        {
                            "turn_id": turn.turn_id,
                            "index": i,
                            "encoding": "base64-text-placeholder",
                            "chunk": out.decode("utf-8", errors="ignore"),
                        },
                    )
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

        await send_event(EVENT_READY, {"message": "connected", "protocol": "v0"})

        try:
            while True:
                raw = await ws.receive_text()

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
                    await send_event(EVENT_READY, {"protocol": "v0", "status": "ok"})
                    continue

                if parsed.event_type == EVENT_CANCEL:
                    if session.current_turn is not None:
                        session.current_turn.cancelled = True
                        continue

                    had_buffered_audio = bool(session.incoming_chunks)
                    session.incoming_chunks.clear()
                    session.incoming_bytes = 0
                    if had_buffered_audio:
                        await finish_turn(turn_id=None, reason="cancelled")
                    continue

                if parsed.event_type == EVENT_AUDIO_IN:
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

                if parsed.event_type == EVENT_AUDIO_END:
                    if session.turn_task is not None:
                        await send_error("TURN_IN_PROGRESS", "A turn is already running")
                        continue

                    chunks = list(session.incoming_chunks)
                    session.incoming_chunks.clear()
                    session.incoming_bytes = 0
                    session.turn_task = asyncio.create_task(run_buffered_turn(chunks))
                    continue

        except WebSocketDisconnect:
            if session.current_turn is not None:
                session.current_turn.cancelled = True
            if session.turn_task is not None:
                session.turn_task.cancel()
            return

    return app


app = create_app()
