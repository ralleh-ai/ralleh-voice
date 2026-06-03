from __future__ import annotations

import base64
from typing import AsyncIterator


class DeterministicVAD:
    """Simple local VAD: any non-whitespace payload is treated as speech."""

    async def detect_speech(self, pcm_chunk: bytes) -> bool:
        return bool(pcm_chunk.strip())


class DeterministicSTT:
    """Lightweight local STT: decode utf-8 text and normalize whitespace."""

    async def transcribe_stream(self, chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
        async for chunk in chunks:
            text = chunk.decode("utf-8", errors="ignore")
            normalized = " ".join(text.split())
            if normalized:
                yield normalized


class DeterministicOpenClawBridge:
    """Local bridge stub for deterministic tests/dev."""

    async def ask(self, prompt: str, session_id: str) -> str:
        clean = " ".join(prompt.split())
        return f"Ralleh stub reply ({session_id}): {clean}"


class DeterministicTTS:
    """Local TTS stub: emits base64 payload as encoded placeholder chunk."""

    event_encoding = "base64-text-placeholder"
    event_sample_rate = None

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        yield encoded.encode("utf-8")
