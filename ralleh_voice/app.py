from __future__ import annotations

import json
import time
import uuid
from typing import Any

from .config import load_settings
from .events import (
    EVENT_AUDIO_OUT_CHUNK,
    EVENT_CANCEL,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_HELLO,
    EVENT_READY,
    event_envelope,
)
from .interfaces import StubOpenClawBridge, StubSTT, StubTTS, StubVAD
from .pipeline import VoicePipeline


def health_payload() -> dict[str, Any]:
    cfg = load_settings()
    return {
        "service": "ralleh-voice",
        "status": "ok",
        "version": "0.1.0",
        "env": cfg.env,
        "components": {
            "vad": "stub",
            "stt": "stub",
            "openclaw_bridge": "stub",
            "tts": "stub",
        },
        "timestamp": int(time.time()),
    }


def readiness_payload() -> dict[str, Any]:
    cfg = load_settings()
    return {
        "service": "ralleh-voice",
        "ready": True,
        "openclaw_gateway_url": cfg.openclaw_gateway_url,
        "note": "Readiness here means process/config ready, not model warm status.",
    }


def create_app():
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    cfg = load_settings()
    app = FastAPI(title="ralleh-voice", version="0.1.0")

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
        session_id = str(uuid.uuid4())
        seq = 0

        await ws.send_text(json.dumps(event_envelope(EVENT_READY, session_id, seq, {"message": "connected"})))
        seq += 1

        pipeline = VoicePipeline(
            vad=StubVAD(),
            stt=StubSTT(),
            bridge=StubOpenClawBridge(),
            tts=StubTTS(),
        )

        async def single_chunk_stream(chunk: bytes):
            yield chunk

        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                typ = msg.get("type")
                payload = msg.get("payload", {})

                if typ == EVENT_HELLO:
                    await ws.send_text(
                        json.dumps(event_envelope(EVENT_READY, session_id, seq, {"protocol": "v0"}))
                    )
                    seq += 1
                    continue

                if typ == EVENT_CANCEL:
                    await ws.send_text(
                        json.dumps(event_envelope(EVENT_DONE, session_id, seq, {"reason": "cancelled"}))
                    )
                    seq += 1
                    continue

                if typ == "audio.input.chunk":
                    # Foundation-only behavior: process a synthetic byte payload.
                    chunk = payload.get("bytes", "").encode("utf-8")
                    async for out in pipeline.run_turn(single_chunk_stream(chunk), session_id=session_id):
                        await ws.send_text(
                            json.dumps(
                                event_envelope(
                                    EVENT_AUDIO_OUT_CHUNK,
                                    session_id,
                                    seq,
                                    {"encoding": "utf-8-placeholder", "chunk": out.decode("utf-8", "ignore")},
                                )
                            )
                        )
                        seq += 1

                    await ws.send_text(json.dumps(event_envelope(EVENT_DONE, session_id, seq, {"reason": "turn-complete"})))
                    seq += 1
                    continue

                await ws.send_text(
                    json.dumps(
                        event_envelope(
                            EVENT_ERROR,
                            session_id,
                            seq,
                            {"code": "UNSUPPORTED_EVENT", "detail": f"unsupported type: {typ}"},
                        )
                    )
                )
                seq += 1

        except WebSocketDisconnect:
            return

    return app


app = create_app()
