from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import AsyncIterator

from .interfaces import OpenClawBridge, STTAdapter, TTSAdapter, VADAdapter


@dataclass(slots=True)
class TurnOutput:
    transcript: str
    reply: str
    audio_chunks: list[bytes]


class PipelineCancelled(RuntimeError):
    """Raised when a running turn is cancelled."""


@dataclass(slots=True)
class TurnState:
    turn_id: int
    cancelled: bool = False


@dataclass(slots=True)
class VoicePipeline:
    vad: VADAdapter
    stt: STTAdapter
    bridge: OpenClawBridge
    tts: TTSAdapter

    async def run_turn(
        self,
        audio_chunks: AsyncIterator[bytes],
        *,
        session_id: str,
        state: TurnState,
    ) -> TurnOutput:
        """
        Deterministic, testable turn pipeline with cancellation checks.
        """
        transcript_parts: list[str] = []

        async for chunk in audio_chunks:
            self._ensure_not_cancelled(state)
            if await self.vad.detect_speech(chunk):
                transcript_parts.append(chunk.decode("utf-8", errors="ignore"))

        self._ensure_not_cancelled(state)

        transcript_source = " ".join(part.strip() for part in transcript_parts if part.strip())
        transcript = transcript_source or "(no transcript)"

        stt_parts: list[str] = []
        async for segment in self.stt.transcribe_stream(_single_text_chunk(transcript)):
            self._ensure_not_cancelled(state)
            cleaned = segment.strip()
            if cleaned:
                stt_parts.append(cleaned)

        final_transcript = " ".join(stt_parts).strip() or transcript

        self._ensure_not_cancelled(state)
        reply = await self.bridge.ask(final_transcript, session_id=session_id)
        self._ensure_not_cancelled(state)

        audio_chunks_out: list[bytes] = []
        async for out in self.tts.synthesize_stream(reply):
            self._ensure_not_cancelled(state)
            audio_chunks_out.append(out)

        return TurnOutput(
            transcript=final_transcript,
            reply=reply,
            audio_chunks=audio_chunks_out,
        )

    @staticmethod
    def _ensure_not_cancelled(state: TurnState) -> None:
        if state.cancelled:
            raise PipelineCancelled("turn cancelled")


async def _single_text_chunk(text: str) -> AsyncIterator[bytes]:
    yield text.encode("utf-8")


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
    """
    Local TTS stub: emits a base64 payload that mimics encoded audio chunk transport.
    """

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        yield encoded.encode("utf-8")


# TODO(adapters): Silero VAD integration point:
# - replace DeterministicVAD with a model-backed adapter and tune endpointing.
# TODO(adapters): Faster-Whisper integration point:
# - stream PCM frames through real STT adapter.
# TODO(adapters): OpenClaw bridge integration point:
# - map session/turn IDs to cancellable OpenClaw conversations.
# TODO(adapters): Kokoro streaming TTS integration point:
# - return real encoded audio frames for low-latency playback.
