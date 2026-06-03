import base64

from fastapi.testclient import TestClient

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
        done = ws.receive_json()
        assert done["type"] == "session.done"
        assert done["payload"]["reason"] == "cancelled"


def test_ws_invalid_base64_chunk():
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": "$$$"}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "BAD_AUDIO_CHUNK"


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
