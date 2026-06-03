import pytest

from ralleh_voice.config import load_settings


def test_load_settings_defaults(monkeypatch):
    monkeypatch.delenv("RALLEH_VOICE_PORT", raising=False)
    cfg = load_settings()
    assert cfg.port == 8099
    assert cfg.ws_path == "/v1/ws/voice"
    assert cfg.adapter_vad == "deterministic"


def test_load_settings_overrides(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_PORT", "9011")
    monkeypatch.setenv("RALLEH_VOICE_STATIC_ENABLED", "false")
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_STT", "stub")
    cfg = load_settings()
    assert cfg.port == 9011
    assert cfg.static_enabled is False
    assert cfg.adapter_stt == "stub"


def test_load_settings_rejects_unknown_adapter(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_VAD", "magic")
    with pytest.raises(ValueError):
        load_settings()
