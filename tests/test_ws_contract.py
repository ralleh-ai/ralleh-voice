import base64

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ralleh_voice.app import create_app


def test_ws_malformed_json_returns_structured_error():
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()  # initial ready
        ws.send_text("{")
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "BAD_JSON"


def test_ws_turn_flow_and_cancel():
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()  # initial ready
        ws.send_json({"type": "session.hello", "payload": {"client": "test"}})
        hello_ack = ws.receive_json()
        assert hello_ack["type"] == "session.ready"

        pcm = base64.b64encode(b"hello world").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": pcm}})
        ws.send_json({"type": "audio.input.end", "payload": {}})

        out = [ws.receive_json() for _ in range(4)]
        types = [item["type"] for item in out]
        assert types == ["stt.final", "agent.reply", "audio.output.chunk", "session.done"]

        ws.send_json({"type": "session.cancel", "payload": {"reason": "barge-in"}})
        ws.send_json({"type": "session.cancel", "payload": {"reason": "barge-in-again"}})


def test_ws_invalid_base64_chunk():
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": "$$$"}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "BAD_AUDIO_CHUNK"


def test_ws_rejects_too_large_event(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_EVENT_BYTES", "1024")
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_text('{"type":"session.hello","payload":{"x":"' + ("y" * 2000) + '"}}')
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "EVENT_TOO_LARGE"


def test_ws_rejects_too_large_audio_chunk(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES", "256")
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        chunk = base64.b64encode(b"a" * 300).decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": chunk}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "AUDIO_CHUNK_TOO_LARGE"


def test_ws_rejects_turn_audio_limit(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_BUFFERED_AUDIO_BYTES", "1024")
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES", "1024")
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        chunk = base64.b64encode(b"a" * 600).decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": chunk}})
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": chunk}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "TURN_BUFFER_OVERFLOW"


def test_ws_rejects_turn_chunk_count_limit(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_BUFFERED_CHUNKS", "1")
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        chunk = base64.b64encode(b"a").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": chunk}})
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": chunk}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "TURN_BUFFER_OVERFLOW"


def test_ws_adapter_failure_returns_structured_error(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_BRIDGE", "openclaw-gateway")

    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()  # initial ready
        pcm = base64.b64encode(b"hello world").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": pcm}})
        ws.send_json({"type": "audio.input.end", "payload": {}})

        err = ws.receive_json()
        done = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "ADAPTER_FAILURE"
        assert err["payload"]["meta"]["component"] == "openclaw_bridge"
        assert done["type"] == "session.done"
        assert done["payload"]["reason"] == "error"


def test_ws_pipeline_failure_redacts_internal_exception(monkeypatch):
    class BoomBridge:
        async def ask(self, prompt: str, session_id: str) -> str:
            raise RuntimeError("sensitive internal detail")

    from ralleh_voice import app as app_module

    original_builder = app_module._build_pipeline

    class _Pipeline:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        async def run_turn(self, audio_chunks, *, session_id, state):
            pipeline = self._wrapped(app_module.load_settings())
            pipeline.bridge = BoomBridge()
            return await pipeline.run_turn(audio_chunks, session_id=session_id, state=state)

    monkeypatch.setattr(app_module, "_build_pipeline", lambda cfg: _Pipeline(original_builder))

    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        pcm = base64.b64encode(b"hello world").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": pcm}})
        ws.send_json({"type": "audio.input.end", "payload": {}})
        err = ws.receive_json()
        done = ws.receive_json()

        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "PIPELINE_FAILURE"
        assert "sensitive internal detail" not in err["payload"]["detail"]
        assert done["type"] == "session.done"
        assert done["payload"]["reason"] == "error"


def test_ws_auth_disabled_dev_path_still_works(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "off")
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "session.ready"
        assert ready["payload"]["session"]["auth_required"] is False

        pcm = base64.b64encode(b"hello world").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": pcm}})
        ws.send_json({"type": "audio.input.end", "payload": {}})
        out = [ws.receive_json() for _ in range(4)]
        assert [item["type"] for item in out] == ["stt.final", "agent.reply", "audio.output.chunk", "session.done"]


def test_ws_auth_enabled_missing_token_blocks_audio(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "shared-secret")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_TOKEN", "dummy-secret")
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        pcm = base64.b64encode(b"hello world").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": pcm}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "AUTH_REQUIRED"


def test_ws_auth_enabled_bad_token_rejected_and_redacted(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "shared-secret")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_TOKEN", "dummy-secret")
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json(
            {
                "type": "session.hello",
                "payload": {"client": "test", "auth_token": "wrong-token"},
            }
        )
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "AUTH_FAILED"
        assert "wrong-token" not in str(err)

        with pytest.raises(WebSocketDisconnect):
            ws.send_json({"type": "session.cancel", "payload": {}})
            ws.receive_json()


def test_ws_auth_enabled_good_token_allows_turn(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "shared-secret")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_TOKEN", "dummy-secret")
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json(
            {
                "type": "session.hello",
                "payload": {"client": "test", "auth_token": "dummy-secret"},
            }
        )
        hello_ack = ws.receive_json()
        assert hello_ack["type"] == "session.ready"
        assert hello_ack["payload"]["session"]["authenticated"] is True

        pcm = base64.b64encode(b"hello world").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": pcm}})
        ws.send_json({"type": "audio.input.end", "payload": {}})
        out = [ws.receive_json() for _ in range(4)]
        assert [item["type"] for item in out] == ["stt.final", "agent.reply", "audio.output.chunk", "session.done"]


def test_ws_rate_limit_event_count(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_MINUTE", "2")
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "session.cancel", "payload": {"reason": "one"}})
        ws.send_json({"type": "session.cancel", "payload": {"reason": "two"}})
        ws.send_json({"type": "session.cancel", "payload": {"reason": "three"}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "RATE_LIMITED"
        assert err["payload"]["meta"]["kind"] == "events_per_minute"


def test_ws_rate_limit_audio_bytes(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_MINUTE", "10")
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES", "1024")
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_BUFFERED_AUDIO_BYTES", "1024")
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        chunk = base64.b64encode(b"1234567890").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": chunk}})

        chunk_over = base64.b64encode(b"x").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": chunk_over}})
        err = ws.receive_json()
        done = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "RATE_LIMITED"
        assert err["payload"]["meta"]["kind"] == "audio_bytes_per_minute"
        assert done["type"] == "session.done"
        assert done["payload"]["reason"] == "rate-limited"
