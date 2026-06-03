from __future__ import annotations

from dataclasses import dataclass
import os


_ALLOWED_VAD = {"deterministic", "stub", "silero"}
_ALLOWED_STT = {"deterministic", "stub", "faster-whisper"}
_ALLOWED_TTS = {"deterministic", "stub", "kokoro"}
_ALLOWED_BRIDGE = {"deterministic", "stub", "openclaw-gateway"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        raise ValueError(f"{name} must be one of {sorted(allowed)}, got: {value}")
    return value


@dataclass(slots=True)
class Settings:
    env: str = "dev"
    host: str = "127.0.0.1"
    port: int = 8099
    log_level: str = "info"
    ws_path: str = "/v1/ws/voice"
    static_enabled: bool = True
    openclaw_gateway_url: str = "http://127.0.0.1:18789"
    openclaw_token_ref: str = "secret:openclaw_gateway_token"
    openclaw_gateway_token_env_var: str = "RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN"
    openclaw_gateway_allow_unauthenticated: bool = False
    openclaw_agent_target: str = "openclaw/default"
    openclaw_session_key_prefix: str = "ralleh-voice"
    openclaw_gateway_timeout_ms: int = 10000
    kokoro_voice: str = "af_bella"
    audio_sample_rate: int = 16000
    adapter_vad: str = "deterministic"
    adapter_stt: str = "deterministic"
    adapter_tts: str = "deterministic"
    adapter_bridge: str = "deterministic"
    faster_whisper_model_ref: str = "model:faster-whisper-tiny"
    faster_whisper_device: str = "cpu"
    faster_whisper_compute_type: str = "int8"
    silero_model_ref: str = "model:silero-vad"
    silero_sample_rate: int = 16000
    silero_threshold: float = 0.5
    silero_min_speech_ms: int = 250
    silero_min_silence_ms: int = 150
    kokoro_model_ref: str = "model:kokoro"
    kokoro_sample_rate: int = 24000
    kokoro_output_format: str = "pcm_s16le"


def load_settings() -> Settings:
    return Settings(
        env=os.getenv("RALLEH_VOICE_ENV", "dev"),
        host=os.getenv("RALLEH_VOICE_HOST", "127.0.0.1"),
        port=int(os.getenv("RALLEH_VOICE_PORT", "8099")),
        log_level=os.getenv("RALLEH_VOICE_LOG_LEVEL", "info"),
        ws_path=os.getenv("RALLEH_VOICE_WS_PATH", "/v1/ws/voice"),
        static_enabled=_env_bool("RALLEH_VOICE_STATIC_ENABLED", True),
        openclaw_gateway_url=os.getenv(
            "RALLEH_VOICE_OPENCLAW_GATEWAY_URL", "http://127.0.0.1:18789"
        ),
        openclaw_token_ref=os.getenv(
            "RALLEH_VOICE_OPENCLAW_TOKEN_REF", "secret:openclaw_gateway_token"
        ),
        openclaw_gateway_token_env_var=os.getenv(
            "RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN_ENV_VAR",
            "RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN",
        ),
        openclaw_gateway_allow_unauthenticated=_env_bool(
            "RALLEH_VOICE_OPENCLAW_GATEWAY_ALLOW_UNAUTHENTICATED", False
        ),
        openclaw_agent_target=os.getenv("RALLEH_VOICE_OPENCLAW_AGENT_TARGET", "openclaw/default"),
        openclaw_session_key_prefix=os.getenv(
            "RALLEH_VOICE_OPENCLAW_SESSION_KEY_PREFIX", "ralleh-voice"
        ),
        openclaw_gateway_timeout_ms=int(
            os.getenv("RALLEH_VOICE_OPENCLAW_GATEWAY_TIMEOUT_MS", "10000")
        ),
        kokoro_voice=os.getenv("RALLEH_VOICE_KOKORO_VOICE", "af_bella"),
        audio_sample_rate=int(os.getenv("RALLEH_VOICE_AUDIO_SAMPLE_RATE", "16000")),
        adapter_vad=_env_choice("RALLEH_VOICE_ADAPTER_VAD", "deterministic", _ALLOWED_VAD),
        adapter_stt=_env_choice("RALLEH_VOICE_ADAPTER_STT", "deterministic", _ALLOWED_STT),
        adapter_tts=_env_choice("RALLEH_VOICE_ADAPTER_TTS", "deterministic", _ALLOWED_TTS),
        adapter_bridge=_env_choice(
            "RALLEH_VOICE_ADAPTER_BRIDGE", "deterministic", _ALLOWED_BRIDGE
        ),
        faster_whisper_model_ref=os.getenv(
            "RALLEH_VOICE_FASTER_WHISPER_MODEL_REF", "model:faster-whisper-tiny"
        ),
        faster_whisper_device=os.getenv("RALLEH_VOICE_FASTER_WHISPER_DEVICE", "cpu"),
        faster_whisper_compute_type=os.getenv(
            "RALLEH_VOICE_FASTER_WHISPER_COMPUTE_TYPE", "int8"
        ),
        silero_model_ref=os.getenv("RALLEH_VOICE_SILERO_MODEL_REF", "model:silero-vad"),
        silero_sample_rate=int(os.getenv("RALLEH_VOICE_SILERO_SAMPLE_RATE", "16000")),
        silero_threshold=float(os.getenv("RALLEH_VOICE_SILERO_THRESHOLD", "0.5")),
        silero_min_speech_ms=int(os.getenv("RALLEH_VOICE_SILERO_MIN_SPEECH_MS", "250")),
        silero_min_silence_ms=int(os.getenv("RALLEH_VOICE_SILERO_MIN_SILENCE_MS", "150")),
        kokoro_model_ref=os.getenv("RALLEH_VOICE_KOKORO_MODEL_REF", "model:kokoro"),
        kokoro_sample_rate=int(os.getenv("RALLEH_VOICE_KOKORO_SAMPLE_RATE", "24000")),
        kokoro_output_format=os.getenv("RALLEH_VOICE_KOKORO_OUTPUT_FORMAT", "pcm_s16le"),
    )
