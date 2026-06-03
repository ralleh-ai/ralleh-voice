from ralleh_voice.app import health_payload, readiness_payload


def test_health_payload_shape():
    payload = health_payload()
    assert payload["service"] == "ralleh-voice"
    assert payload["status"] == "ok"
    assert payload["version"] == "0.2.1"
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
