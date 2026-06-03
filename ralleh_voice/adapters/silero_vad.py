from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import AdapterError


@dataclass(slots=True)
class SileroVADAdapter:
    model_ref: str
    sample_rate: int
    threshold: float
    min_speech_ms: int
    min_silence_ms: int
    _model: object | None = field(default=None, init=False, repr=False)
    _get_speech_timestamps: object | None = field(default=None, init=False, repr=False)

    def _ensure_model(self):
        if self._model is not None and self._get_speech_timestamps is not None:
            return self._model, self._get_speech_timestamps
        try:
            import torch
        except ImportError as exc:
            raise AdapterError(
                code="MISSING_DEPENDENCY",
                detail="Silero VAD adapter requires optional dependency 'torch'.",
                component="vad",
                hint="Install VAD deps with pip install -e .[vad] or the full stack with .[voice]",
                meta={"dependency": "torch", "adapter": "silero", "model_ref": self.model_ref},
            ) from exc

        try:
            from silero_vad import get_speech_timestamps, load_silero_vad  # type: ignore
        except ImportError as exc:
            raise AdapterError(
                code="MISSING_DEPENDENCY",
                detail="Silero VAD adapter requires optional dependency 'silero-vad'.",
                component="vad",
                hint="Install VAD deps with pip install -e .[vad] or the full stack with .[voice]",
                meta={"dependency": "silero-vad", "adapter": "silero", "model_ref": self.model_ref},
            ) from exc

        if self.sample_rate not in {8000, 16000}:
            raise AdapterError(
                code="CONFIG_ERROR",
                detail="Silero VAD supports only 8000 Hz or 16000 Hz sample rates.",
                component="vad",
                hint="Set RALLEH_VOICE_SILERO_SAMPLE_RATE to 8000 or 16000.",
                meta={"adapter": "silero", "sample_rate": self.sample_rate},
            )

        try:
            torch.set_num_threads(1)
            self._model = load_silero_vad()
            self._get_speech_timestamps = get_speech_timestamps
        except Exception as exc:  # pragma: no cover - defensive runtime mapping
            raise AdapterError(
                code="MODEL_INIT_FAILED",
                detail="Silero VAD model bootstrap failed.",
                component="vad",
                hint="Verify Torch/Silero runtime availability and writable model cache paths on this host.",
                meta={
                    "adapter": "silero",
                    "model_ref": self.model_ref,
                    "sample_rate": self.sample_rate,
                },
            ) from exc

        return self._model, self._get_speech_timestamps

    async def detect_speech(self, pcm_chunk: bytes) -> bool:
        if not pcm_chunk.strip():
            return False

        model, get_speech_timestamps = self._ensure_model()

        try:
            import numpy as np
            import torch
        except ImportError as exc:
            raise AdapterError(
                code="MISSING_DEPENDENCY",
                detail="Silero VAD runtime requires numpy and torch to process PCM chunks.",
                component="vad",
                hint="Install VAD deps with pip install -e .[vad] or the full stack with .[voice]",
                meta={"adapter": "silero", "dependency": "numpy/torch"},
            ) from exc

        if len(pcm_chunk) % 2 != 0:
            raise AdapterError(
                code="BAD_AUDIO_CHUNK",
                detail="Silero VAD received PCM chunk with odd byte length.",
                component="vad",
                hint="Provide 16-bit mono PCM audio chunks.",
                meta={"adapter": "silero", "bytes": len(pcm_chunk)},
            )

        try:
            samples = np.frombuffer(pcm_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            audio = torch.from_numpy(samples)
            timestamps = get_speech_timestamps(
                audio,
                model,
                sampling_rate=self.sample_rate,
                threshold=self.threshold,
                min_speech_duration_ms=self.min_speech_ms,
                min_silence_duration_ms=self.min_silence_ms,
            )
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(
                code="UPSTREAM_ERROR",
                detail="Silero VAD failed while processing PCM audio.",
                component="vad",
                hint="Verify PCM format and Silero runtime compatibility.",
                meta={"adapter": "silero", "sample_rate": self.sample_rate},
            ) from exc

        return bool(timestamps)
