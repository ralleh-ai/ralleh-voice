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
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_EVENT_BYTES", "123456")
    cfg = load_settings()
    assert cfg.port == 9011
    assert cfg.static_enabled is False
    assert cfg.adapter_stt == "stub"
    assert cfg.ws_max_event_bytes == 123456


def test_load_settings_rejects_unknown_adapter(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_VAD", "magic")
    with pytest.raises(ValueError):
        load_settings()


def test_load_settings_rejects_invalid_ws_limits(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES", "2048")
    monkeypatch.setenv("RALLEH_VOICE_WS_MAX_BUFFERED_AUDIO_BYTES", "1024")
    with pytest.raises(ValueError):
        load_settings()


def test_load_settings_ws_auth_defaults(monkeypatch):
    monkeypatch.delenv("RALLEH_VOICE_WS_AUTH_MODE", raising=False)
    cfg = load_settings()
    assert cfg.ws_auth_mode == "off"
    assert cfg.ws_auth_token_env_var == "RALLEH_VOICE_WS_AUTH_TOKEN"


def test_load_settings_rejects_shared_secret_without_token(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "shared-secret")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_TOKEN_ENV_VAR", "RALLEH_VOICE_WS_AUTH_TOKEN")
    monkeypatch.delenv("RALLEH_VOICE_WS_AUTH_TOKEN", raising=False)

    with pytest.raises(ValueError):
        load_settings()


def test_load_settings_shared_secret_accepts_env_token(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "shared-secret")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_TOKEN_ENV_VAR", "RALLEH_VOICE_WS_AUTH_TOKEN")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_TOKEN", "dummy-test-token")

    cfg = load_settings()
    assert cfg.ws_auth_mode == "shared-secret"


def test_load_settings_rejects_signed_token_without_key(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "signed-token")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_SIGNING_KEY_ENV_VAR", "RALLEH_VOICE_WS_AUTH_SIGNING_KEY")
    monkeypatch.delenv("RALLEH_VOICE_WS_AUTH_SIGNING_KEY", raising=False)

    with pytest.raises(ValueError):
        load_settings()


def test_load_settings_signed_token_accepts_key(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_MODE", "signed-token")
    monkeypatch.setenv("RALLEH_VOICE_WS_AUTH_SIGNING_KEY", "dummy-signing-key")

    cfg = load_settings()
    assert cfg.ws_auth_mode == "signed-token"
    assert cfg.ws_auth_signing_key_env_var == "RALLEH_VOICE_WS_AUTH_SIGNING_KEY"


def test_load_settings_rate_limit_legacy_alias(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_MINUTE", "321")
    monkeypatch.setenv("RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_MINUTE", "654")

    cfg = load_settings()
    assert cfg.ws_rate_limit_events_per_window == 321
    assert cfg.ws_rate_limit_audio_bytes_per_window == 654


def test_load_settings_rejects_wildcard_origin_when_credentials_enabled(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_CORS_ALLOW_ORIGINS", "*")
    monkeypatch.setenv("RALLEH_VOICE_CORS_ALLOW_CREDENTIALS", "true")
    with pytest.raises(ValueError):
        load_settings()


def test_load_settings_includes_metrics_and_anon_ip_flags(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_METRICS_ENABLED", "true")
    monkeypatch.setenv("RALLEH_VOICE_WS_RATE_LIMIT_INCLUDE_IP_FOR_ANONYMOUS", "true")

    cfg = load_settings()
    assert cfg.metrics_enabled is True
    assert cfg.ws_rate_limit_include_ip_for_anonymous is True
