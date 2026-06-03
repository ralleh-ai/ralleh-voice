from __future__ import annotations

import asyncio
import base64
import binascii
import json
import uuid
from dataclasses import dataclass, field
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
from .pipeline import (
    DeterministicOpenClawBridge,
    DeterministicSTT,
    DeterministicTTS,
    DeterministicVAD,
    PipelineCancelled,
    TurnState,
    VoicePipeline,
)


@dataclass(slots=True)
class SessionState:
    session_id: str
    next_seq: int = 0
    current_turn_id: int = 0
    current_turn: TurnState | None = None
    turn_task: asyncio.Task[None] | None = None
    incoming_chunks: list[bytes] = field(default_factory=list)

    def next(self) -> int:
        seq = self.next_seq
        self.next_seq += 1
        return seq


def health_payload() -> dict[str, Any]:
    cfg = load_settings()
    return {
        "service": "ralleh-voice",
        "status": "ok",
        "version": "0.2.0",
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
    return {
        "service": "ralleh-voice",
        "ready": True,
        "openclaw_gateway_url": cfg.openclaw_gateway_url,
        "note": "Readiness means process/config ready; model warmup is adapter-specific.",
    }


def _build_pipeline(cfg: Settings) -> VoicePipeline:
    # Deterministic adapters are used for the MVP by default.
    # Non-deterministic options are declared/configurable for future integration,
    # but currently map to deterministic placeholders to keep tests lightweight.
    return VoicePipeline(
        vad=DeterministicVAD(),
        stt=DeterministicSTT(),
        bridge=DeterministicOpenClawBridge(),
        tts=DeterministicTTS(),
    )


def create_app():
    cfg = load_settings()
    app = FastAPI(title="ralleh-voice", version="0.2.0")

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

        async def send_error(code: str, detail: str) -> None:
            await send_event(EVENT_ERROR, structured_error(code=code, detail=detail))

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
                await send_event(EVENT_DONE, {"turn_id": turn.turn_id, "reason": "turn-complete"})
            except PipelineCancelled:
                await send_event(EVENT_DONE, {"turn_id": turn.turn_id, "reason": "cancelled"})
            finally:
                session.current_turn = None
                session.turn_task = None

        await send_event(EVENT_READY, {"message": "connected", "protocol": "v0"})

        try:
            while True:
                raw = await ws.receive_text()

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

                    session.incoming_chunks.clear()
                    await send_event(EVENT_DONE, {"reason": "cancelled"})
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

                    session.incoming_chunks.append(chunk)
                    continue

                if parsed.event_type == EVENT_AUDIO_END:
                    if session.turn_task is not None:
                        await send_error("TURN_IN_PROGRESS", "A turn is already running")
                        continue

                    chunks = list(session.incoming_chunks)
                    session.incoming_chunks.clear()
                    session.turn_task = asyncio.create_task(run_buffered_turn(chunks))
                    continue

        except WebSocketDisconnect:
            if session.current_turn is not None:
                session.current_turn.cancelled = True
            return

    return app


app = create_app()
