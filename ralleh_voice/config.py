from __future__ import annotations

from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
    kokoro_voice: str = "af_bella"
    audio_sample_rate: int = 16000


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
        kokoro_voice=os.getenv("RALLEH_VOICE_KOKORO_VOICE", "af_bella"),
        audio_sample_rate=int(os.getenv("RALLEH_VOICE_AUDIO_SAMPLE_RATE", "16000")),
    )
