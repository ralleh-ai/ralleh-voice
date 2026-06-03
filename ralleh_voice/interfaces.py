from __future__ import annotations

from typing import Protocol, AsyncIterator


class VADAdapter(Protocol):
    async def detect_speech(self, pcm_chunk: bytes) -> bool:
        """Return True when speech is detected in this chunk."""


class STTAdapter(Protocol):
    async def transcribe_stream(self, chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Yield partial/final transcript segments from audio chunks."""


class OpenClawBridge(Protocol):
    async def ask(self, prompt: str, session_id: str) -> str:
        """Send transcript text to OpenClaw and return assistant response text."""


class TTSAdapter(Protocol):
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Yield encoded audio chunks."""


class StubVAD:
    async def detect_speech(self, pcm_chunk: bytes) -> bool:
        return bool(pcm_chunk)


class StubSTT:
    async def transcribe_stream(self, chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
        async for _ in chunks:
            yield "TODO: integrate faster-whisper stream"
            break


class StubOpenClawBridge:
    async def ask(self, prompt: str, session_id: str) -> str:
        return (
            "Stub response: OpenClaw bridge not wired yet. "
            "TODO connect gateway session and agent routing."
        )


class StubTTS:
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        # Placeholder bytes only; real audio synthesis is TODO.
        yield f"TODO Kokoro stream for: {text}".encode("utf-8")
