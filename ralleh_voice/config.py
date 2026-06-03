from __future__ import annotations

from dataclasses import dataclass
import os


_ALLOWED_VAD = {"deterministic", "stub", "silero"}
_ALLOWED_STT = {"deterministic", "stub", "faster-whisper"}
_ALLOWED_TTS = {"deterministic", "stub", "kokoro"}
_ALLOWED_BRIDGE = {"deterministic", "stub", "openclaw-gateway"}
_ALLOWED_WS_AUTH_MODE = {"off", "shared-secret", "signed-token"}
_ALLOWED_WS_PROCESSING_MODE = {"buffered", "streaming"}
_ALLOWED_WS_RATE_LIMIT_BACKEND = {"memory", "redis"}


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


def _env_int_min(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    value = default if raw is None else int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got: {value}")
    return value


def _env_int_min_alias(primary: str, aliases: tuple[str, ...], default: int, minimum: int) -> int:
    for key in (primary, *aliases):
        raw = os.getenv(key)
        if raw is not None:
            value = int(raw)
            if value < minimum:
                raise ValueError(f"{key} must be >= {minimum}, got: {value}")
            return value
    if default < minimum:
        raise ValueError(f"{primary} default must be >= {minimum}, got: {default}")
    return default


@dataclass(slots=True)
class Settings:
    env: str = "dev"
    host: str = "127.0.0.1"
    port: int = 8099
    log_level: str = "info"
    ws_path: str = "/v1/ws/voice"
    static_enabled: bool = True
    ws_max_event_bytes: int = 262144
    ws_max_audio_chunk_bytes: int = 262144
    ws_max_buffered_chunks: int = 512
    ws_max_buffered_audio_bytes: int = 8388608
    ws_auth_mode: str = "off"
    ws_auth_token_ref: str = "secret:ws_session_shared_secret"
    ws_auth_token_env_var: str = "RALLEH_VOICE_WS_AUTH_TOKEN"
    ws_auth_signing_key_ref: str = "secret:ws_session_signing_key"
    ws_auth_signing_key_env_var: str = "RALLEH_VOICE_WS_AUTH_SIGNING_KEY"
    ws_auth_token_ttl_seconds: int = 120
    ws_auth_token_issuer: str = ""
    ws_auth_token_audience: str = ""
    ws_processing_mode: str = "buffered"
    ws_streaming_max_pending_chunks: int = 128
    ws_rate_limit_backend: str = "memory"
    ws_rate_limit_window_seconds: int = 60
    ws_rate_limit_events_per_window: int = 600
    ws_rate_limit_audio_bytes_per_window: int = 8388608
    ws_rate_limit_redis_url: str = "redis://127.0.0.1:6379/0"
    ws_rate_limit_redis_key_prefix: str = "ralleh:voice:ratelimit"
    ws_rate_limit_redis_timeout_ms: int = 200
    openclaw_gateway_url: str = "http://127.0.0.1:18789"
    openclaw_token_ref: str = "secret:openclaw_gateway_token"
    openclaw_gateway_token_env_var: str = "RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN"
    openclaw_gateway_allow_unauthenticated: bool = False
    openclaw_agent_target: str = "openclaw/default"
    openclaw_session_key_prefix: str = "ralleh-voice"
    openclaw_gateway_timeout_ms: int = 10000
    openclaw_bridge_prompt_max_chars: int = 12000
    kokoro_voice: str = "af_bella"
    kokoro_lang_code: str = "a"
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


def _validate_settings(cfg: Settings) -> Settings:
    if cfg.ws_max_audio_chunk_bytes > cfg.ws_max_buffered_audio_bytes:
        raise ValueError(
            "RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES must be <= RALLEH_VOICE_WS_MAX_BUFFERED_AUDIO_BYTES"
        )

    if cfg.ws_auth_mode == "shared-secret":
        token_env_var = cfg.ws_auth_token_env_var.strip()
        if not token_env_var:
            raise ValueError("RALLEH_VOICE_WS_AUTH_TOKEN_ENV_VAR must be non-empty when shared-secret auth is enabled")
        if not os.getenv(token_env_var, "").strip():
            raise ValueError(
                f"{token_env_var} must be set to a non-empty token when RALLEH_VOICE_WS_AUTH_MODE=shared-secret"
            )

    if cfg.ws_auth_mode == "signed-token":
        signing_env_var = cfg.ws_auth_signing_key_env_var.strip()
        if not signing_env_var:
            raise ValueError("RALLEH_VOICE_WS_AUTH_SIGNING_KEY_ENV_VAR must be non-empty when signed-token auth is enabled")
        if not os.getenv(signing_env_var, "").strip():
            raise ValueError(
                f"{signing_env_var} must be set to a non-empty key when RALLEH_VOICE_WS_AUTH_MODE=signed-token"
            )

    return cfg


def load_settings() -> Settings:
    cfg = Settings(
        env=os.getenv("RALLEH_VOICE_ENV", "dev"),
        host=os.getenv("RALLEH_VOICE_HOST", "127.0.0.1"),
        port=int(os.getenv("RALLEH_VOICE_PORT", "8099")),
        log_level=os.getenv("RALLEH_VOICE_LOG_LEVEL", "info"),
        ws_path=os.getenv("RALLEH_VOICE_WS_PATH", "/v1/ws/voice"),
        static_enabled=_env_bool("RALLEH_VOICE_STATIC_ENABLED", True),
        ws_max_event_bytes=_env_int_min("RALLEH_VOICE_WS_MAX_EVENT_BYTES", 262144, 1),
        ws_max_audio_chunk_bytes=_env_int_min("RALLEH_VOICE_WS_MAX_AUDIO_CHUNK_BYTES", 262144, 1),
        ws_max_buffered_chunks=_env_int_min("RALLEH_VOICE_WS_MAX_BUFFERED_CHUNKS", 512, 1),
        ws_max_buffered_audio_bytes=_env_int_min(
            "RALLEH_VOICE_WS_MAX_BUFFERED_AUDIO_BYTES", 8388608, 1024
        ),
        ws_auth_mode=_env_choice("RALLEH_VOICE_WS_AUTH_MODE", "off", _ALLOWED_WS_AUTH_MODE),
        ws_auth_token_ref=os.getenv(
            "RALLEH_VOICE_WS_AUTH_TOKEN_REF", "secret:ws_session_shared_secret"
        ),
        ws_auth_token_env_var=os.getenv(
            "RALLEH_VOICE_WS_AUTH_TOKEN_ENV_VAR", "RALLEH_VOICE_WS_AUTH_TOKEN"
        ),
        ws_auth_signing_key_ref=os.getenv(
            "RALLEH_VOICE_WS_AUTH_SIGNING_KEY_REF", "secret:ws_session_signing_key"
        ),
        ws_auth_signing_key_env_var=os.getenv(
            "RALLEH_VOICE_WS_AUTH_SIGNING_KEY_ENV_VAR", "RALLEH_VOICE_WS_AUTH_SIGNING_KEY"
        ),
        ws_auth_token_ttl_seconds=_env_int_min("RALLEH_VOICE_WS_AUTH_TOKEN_TTL_SECONDS", 120, 1),
        ws_auth_token_issuer=os.getenv("RALLEH_VOICE_WS_AUTH_TOKEN_ISSUER", ""),
        ws_auth_token_audience=os.getenv("RALLEH_VOICE_WS_AUTH_TOKEN_AUDIENCE", ""),
        ws_processing_mode=_env_choice(
            "RALLEH_VOICE_WS_PROCESSING_MODE", "buffered", _ALLOWED_WS_PROCESSING_MODE
        ),
        ws_streaming_max_pending_chunks=_env_int_min(
            "RALLEH_VOICE_WS_STREAMING_MAX_PENDING_CHUNKS", 128, 1
        ),
        ws_rate_limit_backend=_env_choice(
            "RALLEH_VOICE_WS_RATE_LIMIT_BACKEND", "memory", _ALLOWED_WS_RATE_LIMIT_BACKEND
        ),
        ws_rate_limit_window_seconds=_env_int_min("RALLEH_VOICE_WS_RATE_LIMIT_WINDOW_SECONDS", 60, 1),
        ws_rate_limit_events_per_window=_env_int_min_alias(
            "RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_WINDOW",
            ("RALLEH_VOICE_WS_RATE_LIMIT_EVENTS_PER_MINUTE",),
            600,
            1,
        ),
        ws_rate_limit_audio_bytes_per_window=_env_int_min_alias(
            "RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_WINDOW",
            ("RALLEH_VOICE_WS_RATE_LIMIT_AUDIO_BYTES_PER_MINUTE",),
            8388608,
            1,
        ),
        ws_rate_limit_redis_url=os.getenv("RALLEH_VOICE_WS_RATE_LIMIT_REDIS_URL", "redis://127.0.0.1:6379/0"),
        ws_rate_limit_redis_key_prefix=os.getenv(
            "RALLEH_VOICE_WS_RATE_LIMIT_REDIS_KEY_PREFIX", "ralleh:voice:ratelimit"
        ),
        ws_rate_limit_redis_timeout_ms=_env_int_min(
            "RALLEH_VOICE_WS_RATE_LIMIT_REDIS_TIMEOUT_MS", 200, 1
        ),
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
        openclaw_gateway_timeout_ms=_env_int_min(
            "RALLEH_VOICE_OPENCLAW_GATEWAY_TIMEOUT_MS", 10000, 1
        ),
        openclaw_bridge_prompt_max_chars=_env_int_min(
            "RALLEH_VOICE_OPENCLAW_BRIDGE_PROMPT_MAX_CHARS", 12000, 1
        ),
        kokoro_voice=os.getenv("RALLEH_VOICE_KOKORO_VOICE", "af_bella"),
        kokoro_lang_code=os.getenv("RALLEH_VOICE_KOKORO_LANG_CODE", "a").strip() or "a",
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
    return _validate_settings(cfg)
