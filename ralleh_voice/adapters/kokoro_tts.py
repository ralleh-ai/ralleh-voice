from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .errors import AdapterError


@dataclass(slots=True)
class KokoroTTSAdapter:
    model_ref: str
    voice: str
    sample_rate: int
    output_format: str
    lang_code: str = "a"
    _engine: object | None = field(default=None, init=False, repr=False)

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        try:
            from kokoro import KPipeline  # type: ignore
        except ImportError as exc:
            raise AdapterError(
                code="MISSING_DEPENDENCY",
                detail="Kokoro TTS adapter requires optional dependency 'kokoro'.",
                component="tts",
                hint="Install Kokoro only with pip install -e .[tts] or the full stack with .[voice]",
                meta={"dependency": "kokoro", "adapter": "kokoro", "model_ref": self.model_ref},
            ) from exc

        if self.output_format != "pcm_s16le":
            raise AdapterError(
                code="CONFIG_ERROR",
                detail="Kokoro TTS currently supports only pcm_s16le output.",
                component="tts",
                hint="Set RALLEH_VOICE_KOKORO_OUTPUT_FORMAT=pcm_s16le.",
                meta={
                    "adapter": "kokoro",
                    "model_ref": self.model_ref,
                    "output_format": self.output_format,
                },
            )

        try:
            self._engine = KPipeline(lang_code=self.lang_code)
        except Exception as exc:  # pragma: no cover - defensive runtime mapping
            raise AdapterError(
                code="MODEL_INIT_FAILED",
                detail="Kokoro pipeline initialization failed.",
                component="tts",
                hint="Verify Kokoro runtime dependencies and language/voice configuration on this host.",
                meta={
                    "adapter": "kokoro",
                    "model_ref": self.model_ref,
                    "lang_code": self.lang_code,
                    "voice": self.voice,
                    "sample_rate": self.sample_rate,
                },
            ) from exc

        return self._engine

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        prompt = " ".join(text.split()).strip()
        if not prompt:
            raise AdapterError(
                code="CONTRACT_MISMATCH",
                detail="Kokoro TTS received empty text after normalization.",
                component="tts",
                hint="Ensure the bridge produced a non-empty reply before synthesis.",
            )

        pipeline = self._ensure_engine()
        try:
            generator = pipeline(prompt, voice=self.voice)
        except Exception as exc:  # pragma: no cover - defensive runtime mapping
            raise AdapterError(
                code="UPSTREAM_ERROR",
                detail="Kokoro synthesis request failed before audio generation.",
                component="tts",
                hint="Verify Kokoro voice selection and runtime model assets.",
                meta={"adapter": "kokoro", "voice": self.voice, "lang_code": self.lang_code},
            ) from exc

        emitted = False
        for item in generator:
            audio = self._extract_audio(item)
            pcm = self._audio_to_pcm_s16le(audio)
            if pcm:
                emitted = True
                yield pcm

        if not emitted:
            raise AdapterError(
                code="EMPTY_AUDIO",
                detail="Kokoro synthesis completed without producing audio.",
                component="tts",
                hint="Check input text, voice selection, and Kokoro runtime assets.",
                meta={"adapter": "kokoro", "voice": self.voice, "lang_code": self.lang_code},
            )

    @staticmethod
    def _extract_audio(item: Any) -> Any:
        if isinstance(item, tuple) and len(item) >= 3:
            return item[2]
        if isinstance(item, dict) and "audio" in item:
            return item["audio"]
        return item

    @staticmethod
    def _audio_to_pcm_s16le(audio: Any) -> bytes:
        if audio is None:
            return b""
        if isinstance(audio, (bytes, bytearray, memoryview)):
            return bytes(audio)
        if hasattr(audio, "detach"):
            audio = audio.detach()
        if hasattr(audio, "cpu"):
            audio = audio.cpu()
        if hasattr(audio, "numpy"):
            audio = audio.numpy()
        if hasattr(audio, "tolist"):
            audio = audio.tolist()

        samples = KokoroTTSAdapter._flatten_samples(audio)
        if not samples:
            return b""

        ints: list[int] = []
        for sample in samples:
            try:
                value = float(sample)
            except (TypeError, ValueError):
                continue
            if -1.0 <= value <= 1.0:
                scaled = int(max(-1.0, min(1.0, value)) * 32767)
            else:
                scaled = int(max(-32768, min(32767, value)))
            ints.append(scaled)

        if not ints:
            return b""

        return struct.pack("<" + ("h" * len(ints)), *ints)

    @staticmethod
    def _flatten_samples(audio: Any) -> list[Any]:
        if isinstance(audio, (list, tuple)):
            flattened: list[Any] = []
            for item in audio:
                if isinstance(item, (list, tuple)):
                    flattened.extend(KokoroTTSAdapter._flatten_samples(item))
                else:
                    flattened.append(item)
            return flattened
        try:
            return list(audio)
        except TypeError:
            return [audio]
