from ralleh_voice.app import health_payload, readiness_payload


def test_health_payload_shape():
    payload = health_payload()
    assert payload["service"] == "ralleh-voice"
    assert payload["status"] == "ok"
    assert payload["version"] == "0.3.0"
    assert "components" in payload


def test_readiness_payload_shape():
    payload = readiness_payload()
    assert payload["service"] == "ralleh-voice"
    assert "adapters" in payload


def test_readiness_payload_reflects_real_adapter_not_ready(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_STT", "faster-whisper")
    payload = readiness_payload()
    assert payload["ready"] is False
    assert payload["adapters"]["stt"]["selected"] == "faster-whisper"
    assert payload["adapters"]["stt"]["ready"] is False


def test_readiness_payload_openclaw_bridge_requires_token(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_BRIDGE", "openclaw-gateway")
    monkeypatch.delenv("RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN", raising=False)
    payload = readiness_payload()

    assert payload["ready"] is False
    bridge = payload["adapters"]["openclaw_bridge"]
    assert bridge["selected"] == "openclaw-gateway"
    assert bridge["ready"] is False
    assert "gateway_token" in bridge["missing"]


def test_readiness_payload_openclaw_bridge_ready_when_token_present(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_BRIDGE", "openclaw-gateway")
    monkeypatch.setenv("RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN", "token")
    payload = readiness_payload()

    bridge = payload["adapters"]["openclaw_bridge"]
    assert bridge["selected"] == "openclaw-gateway"
    assert bridge["ready"] is True
