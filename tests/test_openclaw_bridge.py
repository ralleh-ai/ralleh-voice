import json
import urllib.error

import pytest

from ralleh_voice.adapters.errors import AdapterError
from ralleh_voice.adapters.openclaw_bridge import OpenClawGatewayBridge


class _Response:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _bridge(**kwargs) -> OpenClawGatewayBridge:
    return OpenClawGatewayBridge(
        gateway_url=kwargs.get("gateway_url", "http://127.0.0.1:18789"),
        token_ref=kwargs.get("token_ref", "secret:openclaw_gateway_token"),
        token_env_var=kwargs.get("token_env_var", "RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN"),
        allow_unauthenticated=kwargs.get("allow_unauthenticated", False),
        agent_target=kwargs.get("agent_target", "openclaw/default"),
        session_key_prefix=kwargs.get("session_key_prefix", "ralleh-voice"),
        timeout_ms=kwargs.get("timeout_ms", 2500),
    )


def test_openclaw_bridge_success_path(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN", "super-secret-token")

    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["auth"] = req.headers.get("Authorization")
        captured["session"] = req.headers.get("x-openclaw-session-key") or req.headers.get("X-openclaw-session-key")
        captured["content_type"] = req.headers.get("Content-type")
        captured["timeout"] = timeout
        body = json.loads(req.data.decode("utf-8"))
        captured["body"] = body
        return _Response(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Bridge says hello",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    bridge = _bridge()
    import asyncio

    out = asyncio.run(bridge.ask("  hello world  ", session_id="session-123"))

    assert out == "Bridge says hello"
    assert captured["url"] == "http://127.0.0.1:18789/v1/chat/completions"
    assert captured["auth"] == "Bearer super-secret-token"
    assert captured["content_type"] == "application/json"
    assert captured["timeout"] == 2.5
    assert captured["body"]["model"] == "openclaw/default"
    assert captured["body"]["messages"][0]["content"] == "hello world"
    assert captured["session"].startswith("ralleh-voice:")


def test_openclaw_bridge_timeout(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN", "token")

    def fake_urlopen(req, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    bridge = _bridge(timeout_ms=10)

    import asyncio

    with pytest.raises(AdapterError) as exc:
        asyncio.run(bridge.ask("hello", session_id="sess-1"))

    payload = exc.value.to_payload()
    assert payload["code"] == "TIMEOUT"
    assert payload["component"] == "openclaw_bridge"


def test_openclaw_bridge_redacts_token_from_error(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN", "dont-leak-me")

    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url,
            401,
            "unauthorized",
            hdrs={},
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    bridge = _bridge()

    import asyncio

    with pytest.raises(AdapterError) as exc:
        asyncio.run(bridge.ask("hello", session_id="sess-1"))

    payload = exc.value.to_payload()
    combined = json.dumps(payload)
    assert payload["code"] == "AUTH_FAILED"
    assert "dont-leak-me" not in combined
    assert payload["meta"]["token_ref"] == "secret:openclaw_gateway_token"


def test_openclaw_bridge_missing_token_config(monkeypatch):
    monkeypatch.delenv("RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN", raising=False)

    bridge = _bridge()

    import asyncio

    with pytest.raises(AdapterError) as exc:
        asyncio.run(bridge.ask("hello", session_id="sess-1"))

    payload = exc.value.to_payload()
    assert payload["code"] == "CONFIG_ERROR"
    assert payload["meta"]["token_env_var"] == "RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN"


def test_openclaw_bridge_contract_mismatch(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN", "token")

    def fake_urlopen(req, timeout):
        return _Response({"choices": []})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    bridge = _bridge()

    import asyncio

    with pytest.raises(AdapterError) as exc:
        asyncio.run(bridge.ask("hello", session_id="sess-1"))

    payload = exc.value.to_payload()
    assert payload["code"] == "CONTRACT_MISMATCH"
