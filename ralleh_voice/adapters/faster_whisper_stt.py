from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator

from .errors import AdapterError


@dataclass(slots=True)
class FasterWhisperSTTAdapter:
    model_ref: str
    device: str
    compute_type: str
    _model: object | None = field(default=None, init=False, repr=False)

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise AdapterError(
                code="MISSING_DEPENDENCY",
                detail="Faster-Whisper adapter requires optional dependency 'faster-whisper'.",
                component="stt",
                hint="Install voice extras, e.g. pip install -e .[voice]",
                meta={"dependency": "faster-whisper", "adapter": "faster-whisper", "model_ref": self.model_ref},
            ) from exc

        try:
            self._model = WhisperModel(self.model_ref, device=self.device, compute_type=self.compute_type)
        except Exception as exc:  # pragma: no cover - dependency/model specific
            raise AdapterError(
                code="MODEL_INIT_FAILED",
                detail="Failed to initialize Faster-Whisper model.",
                component="stt",
                hint="Check model_ref/device/compute_type and ensure model files are available locally.",
                meta={
                    "adapter": "faster-whisper",
                    "model_ref": self.model_ref,
                    "device": self.device,
                    "compute_type": self.compute_type,
                    "error": str(exc),
                },
            ) from exc
        return self._model

    async def transcribe_stream(self, chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
        self._ensure_model()
        async for _ in chunks:
            break
        raise AdapterError(
            code="NOT_IMPLEMENTED",
            detail="Streaming PCM -> Faster-Whisper transcription wiring is not implemented yet.",
            component="stt",
            hint="Use deterministic STT adapter for now.",
            meta={"adapter": "faster-whisper", "model_ref": self.model_ref},
        )
        if False:
            yield ""  # pragma: no cover
