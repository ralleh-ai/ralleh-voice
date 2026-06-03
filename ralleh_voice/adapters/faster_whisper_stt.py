from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator

from .errors import AdapterError


@dataclass(slots=True)
class FasterWhisperSTTAdapter:
    model_ref: str
    device: str
    compute_type: str
    sample_rate: int
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
        model = self._ensure_model()

        if self.sample_rate != 16000:
            raise AdapterError(
                code="CONFIG_ERROR",
                detail="Faster-Whisper STT currently expects 16kHz mono PCM input.",
                component="stt",
                hint="Set RALLEH_VOICE_AUDIO_SAMPLE_RATE=16000 until resampling is implemented.",
                meta={"adapter": "faster-whisper", "model_ref": self.model_ref, "sample_rate": self.sample_rate},
            )

        pcm = bytearray()
        async for chunk in chunks:
            if chunk:
                pcm.extend(chunk)

        if not pcm:
            return

        try:
            import numpy as np
        except ImportError as exc:
            raise AdapterError(
                code="MISSING_DEPENDENCY",
                detail="Faster-Whisper transcription requires optional dependency 'numpy'.",
                component="stt",
                hint="Install voice extras, e.g. pip install -e .[voice]",
                meta={"dependency": "numpy", "adapter": "faster-whisper", "model_ref": self.model_ref},
            ) from exc

        try:
            audio = np.frombuffer(bytes(pcm), dtype=np.int16).astype(np.float32) / 32768.0
            segments, _info = model.transcribe(audio, language=None, vad_filter=False)
        except AdapterError:
            raise
        except Exception as exc:  # pragma: no cover - dependency/runtime specific
            raise AdapterError(
                code="TRANSCRIPTION_FAILED",
                detail="Faster-Whisper transcription failed.",
                component="stt",
                hint="Verify PCM input format and local model runtime health.",
                meta={"adapter": "faster-whisper", "model_ref": self.model_ref, "device": self.device},
            ) from exc

        yielded = False
        for segment in segments:
            text = getattr(segment, "text", "")
            cleaned = " ".join(str(text).split()).strip()
            if cleaned:
                yielded = True
                yield cleaned

        if not yielded:
            raise AdapterError(
                code="EMPTY_TRANSCRIPT",
                detail="Faster-Whisper returned no transcript text for the provided audio.",
                component="stt",
                hint="Verify that the input contains audible speech and the selected model is appropriate.",
                meta={"adapter": "faster-whisper", "model_ref": self.model_ref},
            )
