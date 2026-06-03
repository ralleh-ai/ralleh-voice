from ralleh_voice.adapters.deterministic import (
    DeterministicOpenClawBridge,
    DeterministicSTT,
    DeterministicTTS,
    DeterministicVAD,
)
from ralleh_voice.app import _build_pipeline
from ralleh_voice.config import load_settings


def test_build_pipeline_uses_deterministic_defaults(monkeypatch):
    monkeypatch.delenv("RALLEH_VOICE_ADAPTER_VAD", raising=False)
    monkeypatch.delenv("RALLEH_VOICE_ADAPTER_STT", raising=False)
    monkeypatch.delenv("RALLEH_VOICE_ADAPTER_TTS", raising=False)
    monkeypatch.delenv("RALLEH_VOICE_ADAPTER_BRIDGE", raising=False)
    pipeline = _build_pipeline(load_settings())

    assert isinstance(pipeline.vad, DeterministicVAD)
    assert isinstance(pipeline.stt, DeterministicSTT)
    assert isinstance(pipeline.bridge, DeterministicOpenClawBridge)
    assert isinstance(pipeline.tts, DeterministicTTS)
