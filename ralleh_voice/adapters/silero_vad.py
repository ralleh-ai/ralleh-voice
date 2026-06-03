from __future__ import annotations

from dataclasses import dataclass, field

from .errors import AdapterError


@dataclass(slots=True)
class SileroVADAdapter:
    model_ref: str
    sample_rate: int
    threshold: float
    min_speech_ms: int
    min_silence_ms: int
    _model: object | None = field(default=None, init=False, repr=False)

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        try:
            # Optional dependency boundary.
            import torch  # noqa: F401
        except ImportError as exc:
            raise AdapterError(
                code="MISSING_DEPENDENCY",
                detail="Silero VAD adapter requires optional dependency 'torch'.",
                component="vad",
                hint="Install voice extras, e.g. pip install -e .[voice]",
                meta={"dependency": "torch", "adapter": "silero", "model_ref": self.model_ref},
            ) from exc

        # Keep this strict until we lock down model bootstrap paths for production.
        raise AdapterError(
            code="NOT_IMPLEMENTED",
            detail="Silero VAD model bootstrap is not wired in this repository yet.",
            component="vad",
            hint="Set RALLEH_VOICE_ADAPTER_VAD=deterministic for CI/dev until model bootstrap is implemented.",
            meta={
                "adapter": "silero",
                "model_ref": self.model_ref,
                "sample_rate": self.sample_rate,
                "threshold": self.threshold,
                "min_speech_ms": self.min_speech_ms,
                "min_silence_ms": self.min_silence_ms,
            },
        )

    async def detect_speech(self, pcm_chunk: bytes) -> bool:
        self._ensure_model()
        return bool(pcm_chunk.strip())
