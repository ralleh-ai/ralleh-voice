from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable

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
        speech_chunks: list[bytes] = []

        try:
            async for chunk in audio_chunks:
                self._ensure_not_cancelled(state)
                if await self.vad.detect_speech(chunk):
                    speech_chunks.append(chunk)

            self._ensure_not_cancelled(state)

            transcript_source = _best_effort_text(speech_chunks)

            stt_parts: list[str] = []
            async for segment in self.stt.transcribe_stream(_chunk_iter(speech_chunks)):
                self._ensure_not_cancelled(state)
                cleaned = segment.strip()
                if cleaned:
                    stt_parts.append(cleaned)

            final_transcript = " ".join(stt_parts).strip() or transcript_source or "(no transcript)"

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

    async def run_turn_streaming(
        self,
        audio_chunks: AsyncIterator[bytes],
        *,
        session_id: str,
        state: TurnState,
        on_partial_transcript: Callable[[str], Awaitable[None]] | None = None,
        on_final_transcript: Callable[[str], Awaitable[None]] | None = None,
        on_reply: Callable[[str], Awaitable[None]] | None = None,
        on_audio_chunk: Callable[[int, bytes], Awaitable[None]] | None = None,
    ) -> TurnOutput:
        output = await self.run_turn(audio_chunks, session_id=session_id, state=state)

        if on_partial_transcript is not None and output.transcript:
            await on_partial_transcript(output.transcript)

        if on_final_transcript is not None:
            await on_final_transcript(output.transcript)

        if on_reply is not None:
            await on_reply(output.reply)

        if on_audio_chunk is not None:
            for idx, chunk in enumerate(output.audio_chunks):
                self._ensure_not_cancelled(state)
                await on_audio_chunk(idx, chunk)

        return output

    @staticmethod
    def _ensure_not_cancelled(state: TurnState) -> None:
        if state.cancelled:
            raise PipelineCancelled("turn cancelled")


async def _chunk_iter(chunks: list[bytes]) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


def _best_effort_text(chunks: list[bytes]) -> str:
    if not chunks:
        return ""
    text = b" ".join(chunk.strip() for chunk in chunks if chunk.strip()).decode("utf-8", errors="ignore")
    return " ".join(text.split()).strip()
