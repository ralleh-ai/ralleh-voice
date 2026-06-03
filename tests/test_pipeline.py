import asyncio

import pytest

from ralleh_voice.pipeline import (
    DeterministicOpenClawBridge,
    DeterministicSTT,
    DeterministicTTS,
    DeterministicVAD,
    PipelineCancelled,
    TurnState,
    VoicePipeline,
)


async def _iter_chunks(chunks):
    for chunk in chunks:
        yield chunk


def test_pipeline_deterministic_output():
    pipeline = VoicePipeline(
        vad=DeterministicVAD(),
        stt=DeterministicSTT(),
        bridge=DeterministicOpenClawBridge(),
        tts=DeterministicTTS(),
    )
    state = TurnState(turn_id=1)

    result = asyncio.run(
        pipeline.run_turn(
            _iter_chunks([b"hello", b" ", b"world"]),
            session_id="sess-1",
            state=state,
        )
    )

    assert result.transcript == "hello world"
    assert "Ralleh stub reply (sess-1): hello world" in result.reply
    assert len(result.audio_chunks) == 1


def test_pipeline_cancelled_before_reply():
    class CancelledBridge:
        async def ask(self, prompt: str, session_id: str) -> str:
            state.cancelled = True
            return "should not complete"

    pipeline = VoicePipeline(
        vad=DeterministicVAD(),
        stt=DeterministicSTT(),
        bridge=CancelledBridge(),
        tts=DeterministicTTS(),
    )
    state = TurnState(turn_id=7)

    with pytest.raises(PipelineCancelled):
        asyncio.run(
            pipeline.run_turn(
                _iter_chunks([b"test"]),
                session_id="sess-cancel",
                state=state,
            )
        )


def test_pipeline_cancelled_immediately():
    pipeline = VoicePipeline(
        vad=DeterministicVAD(),
        stt=DeterministicSTT(),
        bridge=DeterministicOpenClawBridge(),
        tts=DeterministicTTS(),
    )
    state = TurnState(turn_id=99, cancelled=True)

    with pytest.raises(PipelineCancelled):
        asyncio.run(pipeline.run_turn(_iter_chunks([b"hello"]), session_id="sess-x", state=state))
