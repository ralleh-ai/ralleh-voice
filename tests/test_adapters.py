import asyncio
import base64
import struct
import sys
import types

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
        (
            "RALLEH_VOICE_ADAPTER_STT",
            "faster-whisper",
            "stt",
            "MISSING_DEPENDENCY",
            "faster_whisper",
        ),
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


def test_silero_requires_torch(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_VAD", "silero")
    monkeypatch.setitem(sys.modules, "torch", None)

    cfg = load_settings()
    bundle = build_adapters(cfg)

    with pytest.raises(AdapterError) as exc:
        asyncio.run(bundle.vad.detect_speech(b"\x00\x00\x01\x00"))

    payload = exc.value.to_payload()
    assert payload["code"] == "MISSING_DEPENDENCY"
    assert payload["component"] == "vad"


def test_silero_requires_package(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_VAD", "silero")
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(set_num_threads=lambda n: None, from_numpy=lambda arr: arr))
    monkeypatch.setitem(sys.modules, "silero_vad", None)

    cfg = load_settings()
    bundle = build_adapters(cfg)

    with pytest.raises(AdapterError) as exc:
        asyncio.run(bundle.vad.detect_speech(b"\x00\x00\x01\x00"))

    payload = exc.value.to_payload()
    assert payload["code"] == "MISSING_DEPENDENCY"
    assert payload["component"] == "vad"


def test_silero_rejects_bad_sample_rate(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_VAD", "silero")
    monkeypatch.setenv("RALLEH_VOICE_SILERO_SAMPLE_RATE", "11025")
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(set_num_threads=lambda n: None, from_numpy=lambda arr: arr))
    monkeypatch.setitem(
        sys.modules,
        "silero_vad",
        types.SimpleNamespace(load_silero_vad=lambda: object(), get_speech_timestamps=lambda *args, **kwargs: []),
    )

    cfg = load_settings()
    bundle = build_adapters(cfg)

    with pytest.raises(AdapterError) as exc:
        asyncio.run(bundle.vad.detect_speech(b"\x00\x00\x01\x00"))

    payload = exc.value.to_payload()
    assert payload["code"] == "CONFIG_ERROR"
    assert payload["component"] == "vad"


def test_silero_detects_speech(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_VAD", "silero")
    monkeypatch.setenv("RALLEH_VOICE_SILERO_SAMPLE_RATE", "16000")

    class FakeArray:
        def astype(self, _dtype):
            return self
        def __truediv__(self, _value):
            return self

    fake_numpy = types.SimpleNamespace(int16="int16", float32="float32", frombuffer=lambda data, dtype=None: FakeArray())
    fake_torch = types.SimpleNamespace(set_num_threads=lambda n: None, from_numpy=lambda arr: arr)
    fake_silero = types.SimpleNamespace(
        load_silero_vad=lambda: object(),
        get_speech_timestamps=lambda audio, model, **kwargs: [{"start": 0, "end": 10}],
    )
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "silero_vad", fake_silero)

    cfg = load_settings()
    bundle = build_adapters(cfg)

    out = asyncio.run(bundle.vad.detect_speech(b"\x00\x00\x01\x00" * 8))
    assert out is True


def test_silero_detects_silence(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_VAD", "silero")
    monkeypatch.setenv("RALLEH_VOICE_SILERO_SAMPLE_RATE", "16000")

    class FakeArray:
        def astype(self, _dtype):
            return self
        def __truediv__(self, _value):
            return self

    fake_numpy = types.SimpleNamespace(int16="int16", float32="float32", frombuffer=lambda data, dtype=None: FakeArray())
    fake_torch = types.SimpleNamespace(set_num_threads=lambda n: None, from_numpy=lambda arr: arr)
    fake_silero = types.SimpleNamespace(
        load_silero_vad=lambda: object(),
        get_speech_timestamps=lambda audio, model, **kwargs: [],
    )
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "silero_vad", fake_silero)

    cfg = load_settings()
    bundle = build_adapters(cfg)

    out = asyncio.run(bundle.vad.detect_speech(b"\x00\x00\x01\x00" * 8))
    assert out is False


def test_faster_whisper_requires_16khz(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_STT", "faster-whisper")
    monkeypatch.setenv("RALLEH_VOICE_AUDIO_SAMPLE_RATE", "8000")

    cfg = load_settings()
    bundle = build_adapters(cfg)

    class FakeModel:
        def transcribe(self, audio, language=None, vad_filter=False):
            return [], {}

    class FakeArray:
        def astype(self, _dtype):
            return self
        def __truediv__(self, _value):
            return self

    fake_numpy = types.SimpleNamespace(
        int16="int16",
        float32="float32",
        frombuffer=lambda data, dtype=None: FakeArray(),
    )
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)

    bundle.stt._model = FakeModel()

    async def _chunks():
        yield b"\x00\x00\x01\x00"

    with pytest.raises(AdapterError) as exc:
        asyncio.run(_consume(bundle.stt.transcribe_stream(_chunks())))

    payload = exc.value.to_payload()
    assert payload["code"] == "CONFIG_ERROR"
    assert payload["component"] == "stt"


def test_faster_whisper_transcribes_pcm(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_STT", "faster-whisper")
    monkeypatch.setenv("RALLEH_VOICE_AUDIO_SAMPLE_RATE", "16000")

    cfg = load_settings()
    bundle = build_adapters(cfg)

    class Segment:
        def __init__(self, text):
            self.text = text

    class FakeModel:
        def transcribe(self, audio, language=None, vad_filter=False):
            assert audio is not None
            return [Segment(" hello world ")], {"language": "en"}

    class FakeArray:
        def astype(self, _dtype):
            return self
        def __truediv__(self, _value):
            return self

    fake_numpy = types.SimpleNamespace(
        int16="int16",
        float32="float32",
        frombuffer=lambda data, dtype=None: FakeArray(),
    )
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)

    bundle.stt._model = FakeModel()

    async def _chunks():
        yield (b"\x00\x00\x01\x00" * 8)

    out = asyncio.run(_collect(bundle.stt.transcribe_stream(_chunks())))
    assert out == ["hello world"]


def test_faster_whisper_empty_transcript_is_structured(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_STT", "faster-whisper")
    monkeypatch.setenv("RALLEH_VOICE_AUDIO_SAMPLE_RATE", "16000")

    cfg = load_settings()
    bundle = build_adapters(cfg)

    class FakeModel:
        def transcribe(self, audio, language=None, vad_filter=False):
            return [], {}

    class FakeArray:
        def astype(self, _dtype):
            return self
        def __truediv__(self, _value):
            return self

    fake_numpy = types.SimpleNamespace(
        int16="int16",
        float32="float32",
        frombuffer=lambda data, dtype=None: FakeArray(),
    )
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)

    bundle.stt._model = FakeModel()

    async def _chunks():
        yield (b"\x00\x00\x01\x00" * 8)

    with pytest.raises(AdapterError) as exc:
        asyncio.run(_consume(bundle.stt.transcribe_stream(_chunks())))

    payload = exc.value.to_payload()
    assert payload["code"] == "EMPTY_TRANSCRIPT"
    assert payload["component"] == "stt"


def test_kokoro_tts_synthesizes_pcm(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_TTS", "kokoro")
    monkeypatch.setenv("RALLEH_VOICE_KOKORO_OUTPUT_FORMAT", "pcm_s16le")
    monkeypatch.setenv("RALLEH_VOICE_KOKORO_LANG_CODE", "a")

    class FakeAudio:
        def tolist(self):
            return [0.0, 0.5, -0.5, 1.0]

    class FakePipeline:
        def __init__(self, lang_code):
            assert lang_code == "a"
        def __call__(self, text, voice):
            assert text == "hello world"
            assert voice == "af_bella"
            return iter([("gs", "ps", FakeAudio())])

    monkeypatch.setitem(sys.modules, "kokoro", types.SimpleNamespace(KPipeline=FakePipeline))

    cfg = load_settings()
    bundle = build_adapters(cfg)

    out = asyncio.run(_collect(bundle.tts.synthesize_stream(" hello   world ")))
    assert len(out) == 1
    assert len(out[0]) == 8
    samples = struct.unpack("<4h", out[0])
    assert samples[0] == 0
    assert samples[3] == 32767


def test_silero_rejects_odd_length_pcm(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_VAD", "silero")
    monkeypatch.setenv("RALLEH_VOICE_SILERO_SAMPLE_RATE", "16000")
    monkeypatch.setitem(sys.modules, "numpy", types.SimpleNamespace(int16="int16", float32="float32", frombuffer=lambda data, dtype=None: data))
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(set_num_threads=lambda n: None, from_numpy=lambda arr: arr))
    monkeypatch.setitem(
        sys.modules,
        "silero_vad",
        types.SimpleNamespace(load_silero_vad=lambda: object(), get_speech_timestamps=lambda *args, **kwargs: []),
    )

    cfg = load_settings()
    bundle = build_adapters(cfg)

    with pytest.raises(AdapterError) as exc:
        asyncio.run(bundle.vad.detect_speech(b"\x00"))

    payload = exc.value.to_payload()
    assert payload["code"] == "BAD_AUDIO_CHUNK"
    assert payload["component"] == "vad"


def test_kokoro_tts_rejects_unsupported_output_format(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_TTS", "kokoro")
    monkeypatch.setenv("RALLEH_VOICE_KOKORO_OUTPUT_FORMAT", "wav")
    monkeypatch.setenv("RALLEH_VOICE_KOKORO_ALLOW_FALLBACK", "false")
    monkeypatch.setitem(sys.modules, "kokoro", types.SimpleNamespace(KPipeline=lambda lang_code: object()))

    cfg = load_settings()
    bundle = build_adapters(cfg)

    with pytest.raises(AdapterError) as exc:
        asyncio.run(_consume(bundle.tts.synthesize_stream("hello")))

    payload = exc.value.to_payload()
    assert payload["code"] == "CONFIG_ERROR"
    assert payload["component"] == "tts"


def test_kokoro_strict_mode_keeps_real_adapter_when_probe_fails(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_TTS", "kokoro")
    monkeypatch.setenv("RALLEH_VOICE_KOKORO_ALLOW_FALLBACK", "false")
    monkeypatch.setitem(sys.modules, "kokoro", None)

    cfg = load_settings()
    bundle = build_adapters(cfg)

    assert bundle.status["tts"]["selected"] == "kokoro"
    assert bundle.status["tts"]["degraded"] is True
    assert bundle.status["tts"]["active"] == "kokoro-strict"
    with pytest.raises(AdapterError) as exc:
        asyncio.run(_consume(bundle.tts.synthesize_stream("hello")))
    assert exc.value.to_payload()["code"] == "MISSING_DEPENDENCY"


def test_kokoro_falls_back_to_deterministic_when_probe_fails(monkeypatch):
    monkeypatch.setenv("RALLEH_VOICE_ADAPTER_TTS", "kokoro")
    monkeypatch.setenv("RALLEH_VOICE_KOKORO_ALLOW_FALLBACK", "true")
    monkeypatch.setitem(sys.modules, "kokoro", None)

    cfg = load_settings()
    bundle = build_adapters(cfg)

    assert bundle.status["tts"]["selected"] == "kokoro"
    assert bundle.status["tts"]["degraded"] is True
    assert bundle.status["tts"]["active"] == "deterministic-fallback"
    out = asyncio.run(_collect(bundle.tts.synthesize_stream("hello")))
    assert len(out) == 1


async def _collect(stream):
    out = []
    async for item in stream:
        out.append(item)
    return out


async def _consume(stream):
    async for _ in stream:
        pass
