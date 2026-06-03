from __future__ import annotations

from typing import AsyncIterator, Protocol


class VADAdapter(Protocol):
    async def detect_speech(self, pcm_chunk: bytes) -> bool:
        """Return True when speech is detected in this chunk."""


class STTAdapter(Protocol):
    async def transcribe_stream(self, chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Yield transcript segments from incoming audio chunks."""


class OpenClawBridge(Protocol):
    async def ask(self, prompt: str, session_id: str) -> str:
        """Send transcript text to OpenClaw and return response text."""


class TTSAdapter(Protocol):
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Yield encoded audio chunks."""
