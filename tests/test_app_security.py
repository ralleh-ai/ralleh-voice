from fastapi.testclient import TestClient

from ralleh_voice import __version__
from ralleh_voice.app import create_app


def test_health_uses_package_version():
    app = create_app()
    client = TestClient(app)

    resp = client.get("/v1/healthz")
    assert resp.status_code == 200
    assert resp.json()["version"] == __version__


def test_http_security_headers_enabled_by_default():
    app = create_app()
    client = TestClient(app)

    resp = client.get("/v1/healthz")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"
    assert resp.headers["permissions-policy"] == "microphone=(self)"
    assert resp.headers["cache-control"] == "no-store"


def test_http_security_headers_can_be_disabled(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_SECURITY_HEADERS_ENABLED", "false")
    app = create_app()
    client = TestClient(app)

    resp = client.get("/v1/healthz")
    assert "x-content-type-options" not in resp.headers


def test_cors_allow_origin_uses_config(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_CORS_ALLOW_ORIGINS", "https://control.example.com")
    app = create_app()
    client = TestClient(app)

    resp = client.options(
        "/v1/healthz",
        headers={
            "Origin": "https://control.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://control.example.com"


def test_metrics_endpoint_disabled_by_default():
    app = create_app()
    client = TestClient(app)

    resp = client.get("/v1/metrics")
    assert resp.status_code == 404


def test_metrics_endpoint_enabled(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_METRICS_ENABLED", "true")
    app = create_app()
    client = TestClient(app)

    resp = client.get("/v1/metrics")
    assert resp.status_code == 200
    assert "ralleh_voice_ws_connections_total" in resp.text


def test_health_includes_build_commit_when_configured(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_BUILD_COMMIT", "abc123")
    app = create_app()
    client = TestClient(app)

    resp = client.get("/v1/healthz")
    assert resp.status_code == 200
    assert resp.json()["build_commit"] == "abc123"
