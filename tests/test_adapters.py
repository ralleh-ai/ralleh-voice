import asyncio
import sys

import pytest

from ralleh_voice.adapters.errors import AdapterError
from ralleh_voice.adapters.factory import build_adapters
from ralleh_voice.config import load_settings


def test_adapter_factory_defaults_are_deterministic(monkeypatch):
    monkeypatch.delenv("RALLEH_VOICE_ADAPTER_VAD", raising=False)
    monkeypatch.delenv("RALLEH_VOICE_ADAPTER_STT", raising=False)
    monkeypatch.delenv("RALLEH_VOICE_ADAPTER_TTS", raising=False)
    monkeypatch.delenv("RALLEH_VOICE_ADAPTER_BRIDGE", raising=False)
    cfg = load_settings()
    bundle = build_adapters(cfg)

    assert bundle.status["vad"]["ready"] is True
    assert bundle.status["stt"]["ready"] is True
    assert bundle.status["tts"]["ready"] is True
    assert bundle.status["openclaw_bridge"]["ready"] is True


@pytest.mark.parametrize(
    "env_name,env_value,component,expected_code,module_to_block",
    [
        ("RALLEH_VOICE_ADAPTER_VAD", "silero", "vad", "MISSING_DEPENDENCY", "torch"),
        (
            "RALLEH_VOICE_ADAPTER_STT",
            "faster-whisper",
            "stt",
            "MISSING_DEPENDENCY",
            "faster_whisper",
        ),
        ("RALLEH_VOICE_ADAPTER_TTS", "kokoro", "tts", "MISSING_DEPENDENCY", "kokoro"),
        ("RALLEH_VOICE_ADAPTER_BRIDGE", "openclaw-gateway", "openclaw_bridge", "CONFIG_ERROR", None),
    ],
)
def test_real_adapter_failures_are_structured(
    monkeypatch, env_name, env_value, component, expected_code, module_to_block
):
    monkeypatch.setenv(env_name, env_value)
    if module_to_block:
        monkeypatch.setitem(sys.modules, module_to_block, None)

    cfg = load_settings()
    bundle = build_adapters(cfg)

    if component == "vad":
        coro = bundle.vad.detect_speech(b"hello")
    elif component == "stt":

        async def _stt_call():
            async def _chunks():
                yield b"hello"

            async for _ in bundle.stt.transcribe_stream(_chunks()):
                pass

        coro = _stt_call()
    elif component == "tts":

        async def _tts_call():
            async for _ in bundle.tts.synthesize_stream("hello"):
                pass

        coro = _tts_call()
    else:
        coro = bundle.bridge.ask("hello", session_id="sess-1")

    with pytest.raises(AdapterError) as exc:
        asyncio.run(coro)

    payload = exc.value.to_payload()
    assert payload["code"] == expected_code
    assert payload["component"] == component
