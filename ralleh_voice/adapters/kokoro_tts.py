from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator

from .errors import AdapterError


@dataclass(slots=True)
class KokoroTTSAdapter:
    model_ref: str
    voice: str
    sample_rate: int
    output_format: str
    _engine: object | None = field(default=None, init=False, repr=False)

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        try:
            import kokoro  # type: ignore  # noqa: F401
        except ImportError as exc:
            raise AdapterError(
                code="MISSING_DEPENDENCY",
                detail="Kokoro TTS adapter requires optional dependency 'kokoro'.",
                component="tts",
                hint="Install voice extras, e.g. pip install -e .[voice]",
                meta={"dependency": "kokoro", "adapter": "kokoro", "model_ref": self.model_ref},
            ) from exc

        raise AdapterError(
            code="NOT_IMPLEMENTED",
            detail="Kokoro runtime synthesis wiring is not implemented yet.",
            component="tts",
            hint="Use deterministic TTS adapter for now.",
            meta={
                "adapter": "kokoro",
                "model_ref": self.model_ref,
                "voice": self.voice,
                "sample_rate": self.sample_rate,
                "output_format": self.output_format,
            },
        )

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        self._ensure_engine()
        _ = text
        if False:
            yield b""  # pragma: no cover
