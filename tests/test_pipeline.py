import asyncio

import pytest

from ralleh_voice.adapters.deterministic import (
    DeterministicOpenClawBridge,
    DeterministicSTT,
    DeterministicTTS,
    DeterministicVAD,
)
from ralleh_voice.adapters.errors import AdapterError
from ralleh_voice.pipeline import (
    PipelineAdapterFailure,
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


def test_pipeline_wraps_adapter_error():
    class FailingBridge:
        async def ask(self, prompt: str, session_id: str) -> str:
            raise AdapterError(
                code="MISSING_ENDPOINT",
                detail="No endpoint",
                component="openclaw_bridge",
                hint="Configure bridge",
            )

    pipeline = VoicePipeline(
        vad=DeterministicVAD(),
        stt=DeterministicSTT(),
        bridge=FailingBridge(),
        tts=DeterministicTTS(),
    )

    with pytest.raises(PipelineAdapterFailure) as exc:
        asyncio.run(pipeline.run_turn(_iter_chunks([b"hello"]), session_id="sess-err", state=TurnState(turn_id=3)))

    assert exc.value.error.code == "MISSING_ENDPOINT"
