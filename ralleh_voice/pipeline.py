from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

from .adapters.errors import AdapterError
from .interfaces import OpenClawBridge, STTAdapter, TTSAdapter, VADAdapter


@dataclass(slots=True)
class TurnOutput:
    transcript: str
    reply: str
    audio_chunks: list[bytes]


class PipelineCancelled(RuntimeError):
    """Raised when a running turn is cancelled."""


class PipelineAdapterFailure(RuntimeError):
    """Raised when an adapter fails with structured context."""

    def __init__(self, error: AdapterError):
        super().__init__(error.detail)
        self.error = error


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
        transcript_parts: list[str] = []

        try:
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
        except AdapterError as exc:
            raise PipelineAdapterFailure(exc) from exc

    @staticmethod
    def _ensure_not_cancelled(state: TurnState) -> None:
        if state.cancelled:
            raise PipelineCancelled("turn cancelled")


async def _single_text_chunk(text: str) -> AsyncIterator[bytes]:
    yield text.encode("utf-8")
