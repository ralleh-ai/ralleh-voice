import base64
import sys
import time
import types

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ralleh_voice import app as app_module
from ralleh_voice.auth_tokens import mint_signed_session_token


def test_ws_malformed_json_returns_structured_error():
    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()  # initial ready
        ws.send_text("{")
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "BAD_JSON"


def test_ws_rejects_unknown_event_fields_as_bad_event():
    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "session.hello", "payload": {"client": "test"}, "unexpected": True})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "BAD_EVENT"


def test_ws_turn_flow_and_cancel():
    app = app_module.create_app()
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
    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": "$$$"}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "BAD_AUDIO_CHUNK"


def test_ws_rejects_too_large_event(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_EVENT_BYTES", "1024")
    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_text('{"type":"session.hello","payload":{"x":"' + ("y" * 2000) + '"}}')
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "EVENT_TOO_LARGE"


def test_ws_rejects_too_large_audio_chunk(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES", "256")
    app = app_module.create_app()
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
    app = app_module.create_app()
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
    app = app_module.create_app()
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

    app = app_module.create_app()
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
    app = app_module.create_app()
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


def test_ws_kokoro_emits_base64_pcm_chunk(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "off")
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_TTS", "kokoro")
    monkeypatch.setenv("RALLEH_VOICE_KOKORO_OUTPUT_FORMAT", "pcm_s16le")
    monkeypatch.setenv("RALLEH_VOICE_KOKORO_SAMPLE_RATE", "24000")

    class FakeAudio:
        def tolist(self):
            return [0.0, 0.25, -0.25, 1.0]

    class FakePipeline:
        def __init__(self, lang_code):
            assert lang_code == "a"
        def __call__(self, text, voice):
            return iter([("gs", "ps", FakeAudio())])

    monkeypatch.setitem(sys.modules, "kokoro", types.SimpleNamespace(KPipeline=FakePipeline))

    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        pcm = base64.b64encode(b"hello world").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": pcm}})
        ws.send_json({"type": "audio.input.end", "payload": {}})

        events = [ws.receive_json() for _ in range(4)]
        audio = events[2]
        assert audio["type"] == "audio.output.chunk"
        assert audio["payload"]["encoding"] == "base64-pcm_s16le"
        assert audio["payload"]["sample_rate"] == 24000
        assert base64.b64decode(audio["payload"]["chunk"])


def test_ws_kokoro_fallback_uses_placeholder_chunk(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "off")
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_TTS", "kokoro")
    monkeypatch.setenv("RALLEH_VOICE_KOKORO_ALLOW_FALLBACK", "true")
    monkeypatch.setitem(sys.modules, "kokoro", None)

    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        pcm = base64.b64encode(b"hello world").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": pcm}})
        ws.send_json({"type": "audio.input.end", "payload": {}})

        events = [ws.receive_json() for _ in range(4)]
        audio = events[2]
        assert audio["type"] == "audio.output.chunk"
        assert audio["payload"]["encoding"] == "base64-text-placeholder"


def test_ws_auth_enabled_missing_token_blocks_audio(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "shared-secret")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_TOKEN", "dummy-secret")
    app = app_module.create_app()
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
    app = app_module.create_app()
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
        assert err["payload"]["code"] == "AUTH_BAD_SIGNATURE"
        assert "wrong-token" not in str(err)

        with pytest.raises(WebSocketDisconnect):
            ws.send_json({"type": "session.cancel", "payload": {}})
            ws.receive_json()


def test_ws_auth_enabled_good_token_allows_turn(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "shared-secret")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_TOKEN", "dummy-secret")
    app = app_module.create_app()
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


def test_ws_signed_token_success(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "signed-token")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_SIGNING_KEY", "dummy-signing-key")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_TOKEN_ISSUER", "ralleh")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_TOKEN_AUDIENCE", "voice")

    token = mint_signed_session_token(
        session_id="s-1",
        client="browser",
        key="dummy-signing-key",
        ttl_seconds=60,
        now=int(time.time()),
        issuer="ralleh",
        audience="voice",
    )

    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "session.hello", "payload": {"client": "browser", "auth_token": token}})
        ready = ws.receive_json()
        assert ready["type"] == "session.ready"
        assert ready["payload"]["session"]["authenticated"] is True
        assert ready["payload"]["session"]["claims"]["sid"] == "s-1"


def test_ws_signed_token_expired(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "signed-token")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_SIGNING_KEY", "dummy-signing-key")

    token = mint_signed_session_token(
        session_id="s-1",
        client="browser",
        key="dummy-signing-key",
        ttl_seconds=1,
        now=int(time.time()) - 120,
    )

    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "session.hello", "payload": {"client": "browser", "auth_token": token}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "AUTH_EXPIRED"


def test_ws_signed_token_tampered_redacted(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "signed-token")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_SIGNING_KEY", "dummy-signing-key")

    token = mint_signed_session_token(
        session_id="s-1",
        client="browser",
        key="dummy-signing-key",
        ttl_seconds=60,
        now=int(time.time()),
    )
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.AAAA"

    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "session.hello", "payload": {"client": "browser", "auth_token": tampered}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "AUTH_BAD_SIGNATURE"
        assert "dummy-signing-key" not in str(err)
        assert tampered not in str(err)


def test_ws_rate_limit_event_count(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_WINDOW", "2")
    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "session.cancel", "payload": {"reason": "one"}})
        ws.send_json({"type": "session.cancel", "payload": {"reason": "two"}})
        ws.send_json({"type": "session.cancel", "payload": {"reason": "three"}})
        err = ws.receive_json()
        assert err["type"] == "session.error"
        assert err["payload"]["code"] == "RATE_LIMITED"
        assert err["payload"]["meta"]["kind"] == "events_per_window"


def test_ws_rate_limit_audio_bytes(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_WINDOW", "10")
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES", "1024")
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_BUFFERED_AUDIO_BYTES", "1024")
    app = app_module.create_app()
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
        assert err["payload"]["meta"]["kind"] == "audio_bytes_per_window"
        assert done["type"] == "session.done"
        assert done["payload"]["reason"] == "rate-limited"


def test_ws_streaming_mode_emits_partial_before_final(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_PROCESSING_MODE", "streaming")
    monkeypatch.setenv("RALLEH_VOICE_WS_STREAMING_MAX_PENDING_CHUNKS", "8")

    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ready = ws.receive_json()
        assert ready["payload"]["session"]["processing_mode"] == "streaming"

        ws.send_json({"type": "session.hello", "payload": {"client": "streamer"}})
        ws.receive_json()

        pcm = base64.b64encode(b"hello world").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": pcm}})
        ws.send_json({"type": "audio.input.end", "payload": {}})

        out = [ws.receive_json() for _ in range(5)]
        assert [item["type"] for item in out] == [
            "stt.partial",
            "stt.final",
            "agent.reply",
            "audio.output.chunk",
            "session.done",
        ]


def test_ws_initial_ready_exposes_degraded_rate_limit_metadata(monkeypatch):
    class FakeRateLimiter:
        backend = "memory"
        detail = "redis unavailable"

        def allow_event(self, _identity, _now):
            return app_module.RateLimitResult(allowed=True, observed=0, backend="memory", degraded=True, detail=self.detail)

        def allow_audio_bytes(self, _identity, _size, _now):
            return app_module.RateLimitResult(allowed=True, observed=0, backend="memory", degraded=True, detail=self.detail)

    monkeypatch.setattr(app_module, "build_rate_limiter", lambda _cfg: FakeRateLimiter())

    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "session.ready"
        limits = ready["payload"]["session"]["rate_limits"]
        assert limits["degraded"] is True
        assert limits["detail"] == "redis unavailable"


def test_ws_rate_limit_identity_can_include_client_ip_for_anonymous(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_RATE_LIMIT_INCLUDE_IP_FOR_ANONYMOUS", "true")

    seen_identities: list[str] = []

    class IdentityCaptureRateLimiter:
        backend = "memory"
        detail = ""

        def allow_event(self, identity, _now):
            seen_identities.append(identity)
            return app_module.RateLimitResult(allowed=True, observed=1, backend="memory", degraded=False, detail=None)

        def allow_audio_bytes(self, _identity, _size, _now):
            return app_module.RateLimitResult(allowed=True, observed=1, backend="memory", degraded=False, detail=None)

    monkeypatch.setattr(app_module, "build_rate_limiter", lambda _cfg: IdentityCaptureRateLimiter())

    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "session.hello", "payload": {"client": "ip-test"}})
        ws.receive_json()

    assert seen_identities
    assert any(identity.startswith("anon:testclient:") for identity in seen_identities)


def test_ws_streaming_mode_cancel_still_works(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_PROCESSING_MODE", "streaming")

    class SlowStreamingPipeline:
        async def run_turn_streaming(self, audio_chunks, *, session_id, state, **_callbacks):
            async for _ in audio_chunks:
                while not state.cancelled:
                    await __import__("asyncio").sleep(0.01)
            raise app_module.PipelineCancelled("cancelled")

    monkeypatch.setattr(app_module, "_build_pipeline", lambda _cfg: SlowStreamingPipeline())

    app = app_module.create_app()
    client = TestClient(app)

    with client.websocket_connect("/v1/ws/voice") as ws:
        ws.receive_json()
        ws.send_json({"type": "session.hello", "payload": {"client": "streamer"}})
        ws.receive_json()

        pcm = base64.b64encode(b"hello").decode("ascii")
        ws.send_json({"type": "audio.input.chunk", "payload": {"pcm_b64": pcm}})
        ws.send_json({"type": "session.cancel", "payload": {"reason": "barge-in"}})
        ws.send_json({"type": "audio.input.end", "payload": {}})

        done = ws.receive_json()
        assert done["type"] == "session.done"
        assert done["payload"]["reason"] == "cancelled"
