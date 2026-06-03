from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ralleh_voice.config import Settings
from ralleh_voice.interfaces import OpenClawBridge, STTAdapter, TTSAdapter, VADAdapter

from .deterministic import (
    DeterministicOpenClawBridge,
    DeterministicSTT,
    DeterministicTTS,
    DeterministicVAD,
)
from .faster_whisper_stt import FasterWhisperSTTAdapter
from .kokoro_tts import KokoroTTSAdapter
from .openclaw_bridge import OpenClawGatewayBridge
from .silero_vad import SileroVADAdapter


@dataclass(slots=True)
class AdapterBundle:
    vad: VADAdapter
    stt: STTAdapter
    bridge: OpenClawBridge
    tts: TTSAdapter
    status: dict[str, dict[str, Any]]


def build_adapters(cfg: Settings) -> AdapterBundle:
    vad = _build_vad(cfg)
    stt = _build_stt(cfg)
    bridge = _build_bridge(cfg)
    tts = _build_tts(cfg)
    return AdapterBundle(
        vad=vad,
        stt=stt,
        bridge=bridge,
        tts=tts,
        status={
            "vad": _status_for("vad", cfg.adapter_vad),
            "stt": _status_for("stt", cfg.adapter_stt),
            "openclaw_bridge": _status_for("openclaw_bridge", cfg.adapter_bridge),
            "tts": _status_for("tts", cfg.adapter_tts),
        },
    )


def _status_for(component: str, selected: str) -> dict[str, Any]:
    if selected in {"deterministic", "stub"}:
        return {"component": component, "selected": selected, "ready": True, "mode": "deterministic"}
    return {
        "component": component,
        "selected": selected,
        "ready": False,
        "mode": "real-optional",
        "note": "Lazy optional adapter selected; readiness is runtime-dependent.",
    }


def _build_vad(cfg: Settings) -> VADAdapter:
    if cfg.adapter_vad in {"deterministic", "stub"}:
        return DeterministicVAD()
    if cfg.adapter_vad == "silero":
        return SileroVADAdapter(
            model_ref=cfg.silero_model_ref,
            sample_rate=cfg.silero_sample_rate,
            threshold=cfg.silero_threshold,
            min_speech_ms=cfg.silero_min_speech_ms,
            min_silence_ms=cfg.silero_min_silence_ms,
        )
    raise ValueError(f"Unsupported VAD adapter: {cfg.adapter_vad}")


def _build_stt(cfg: Settings) -> STTAdapter:
    if cfg.adapter_stt in {"deterministic", "stub"}:
        return DeterministicSTT()
    if cfg.adapter_stt == "faster-whisper":
        return FasterWhisperSTTAdapter(
            model_ref=cfg.faster_whisper_model_ref,
            device=cfg.faster_whisper_device,
            compute_type=cfg.faster_whisper_compute_type,
        )
    raise ValueError(f"Unsupported STT adapter: {cfg.adapter_stt}")


def _build_bridge(cfg: Settings) -> OpenClawBridge:
    if cfg.adapter_bridge in {"deterministic", "stub"}:
        return DeterministicOpenClawBridge()
    if cfg.adapter_bridge == "openclaw-gateway":
        return OpenClawGatewayBridge(
            gateway_url=cfg.openclaw_gateway_url,
            token_ref=cfg.openclaw_token_ref,
            token_env_var=cfg.openclaw_gateway_token_env_var,
            allow_unauthenticated=cfg.openclaw_gateway_allow_unauthenticated,
            agent_target=cfg.openclaw_agent_target,
            session_key_prefix=cfg.openclaw_session_key_prefix,
            timeout_ms=cfg.openclaw_gateway_timeout_ms,
        )
    raise ValueError(f"Unsupported bridge adapter: {cfg.adapter_bridge}")


def _build_tts(cfg: Settings) -> TTSAdapter:
    if cfg.adapter_tts in {"deterministic", "stub"}:
        return DeterministicTTS()
    if cfg.adapter_tts == "kokoro":
        return KokoroTTSAdapter(
            model_ref=cfg.kokoro_model_ref,
            voice=cfg.kokoro_voice,
            sample_rate=cfg.kokoro_sample_rate,
            output_format=cfg.kokoro_output_format,
        )
    raise ValueError(f"Unsupported TTS adapter: {cfg.adapter_tts}")
