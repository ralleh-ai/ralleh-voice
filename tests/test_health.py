from ralleh_voice.app import health_payload, readiness_payload


def test_health_payload_shape():
    payload = health_payload()
    assert payload["service"] == "ralleh-voice"
    assert payload["status"] == "ok"
    assert payload["version"] == "0.2.0"
    assert "components" in payload


def test_readiness_payload_shape():
    payload = readiness_payload()
    assert payload["service"] == "ralleh-voice"
    assert payload["ready"] is True
