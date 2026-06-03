from fastapi.testclient import TestClient

from ralleh_voice.app import create_app
import scripts.smoke_check as smoke_check
from scripts.smoke_check import check_health, check_ready, check_static, derive_ws_url, path_url


def test_derive_ws_url_http():
    assert derive_ws_url("http://127.0.0.1:8099", "/v1/ws/voice") == "ws://127.0.0.1:8099/v1/ws/voice"


def test_derive_ws_url_https():
    assert derive_ws_url("https://voice.example.com", "/v1/ws/voice") == "wss://voice.example.com/v1/ws/voice"


def test_path_url_keeps_base_path_prefix():
    assert path_url("https://voice.example.com/voice", "/v1/healthz") == "https://voice.example.com/voice/v1/healthz"


def test_health_smoke_against_live_test_server(monkeypatch):
    app = create_app()

    with TestClient(app) as client:
        monkeypatch.setattr(smoke_check, "fetch_json", lambda url, timeout: client.get(url).json())
        result = check_health(str(client.base_url), timeout=5.0)
        assert result.ok is True


def test_ready_smoke_accepts_not_ready_when_allowed(monkeypatch):
    app = create_app()

    with TestClient(app) as client:
        monkeypatch.setattr(smoke_check, "fetch_json", lambda url, timeout: client.get(url).json())
        result = check_ready(str(client.base_url), timeout=5.0, require_ready=False)
        assert result.ok is True


def test_static_smoke_against_live_test_server(monkeypatch):
    app = create_app()

    with TestClient(app) as client:
        monkeypatch.setattr(smoke_check, "fetch_text", lambda url, timeout: client.get(url).text)
        result = check_static(str(client.base_url), timeout=5.0)
        assert result.ok is True
