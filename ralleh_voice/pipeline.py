from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

from .interfaces import VADAdapter, STTAdapter, OpenClawBridge, TTSAdapter


@dataclass(slots=True)
class VoicePipeline:
    vad: VADAdapter
    stt: STTAdapter
    bridge: OpenClawBridge
    tts: TTSAdapter

    async def run_turn(self, audio_chunks: AsyncIterator[bytes], session_id: str) -> AsyncIterator[bytes]:
        """
        Minimal contract-oriented turn pipeline:
        - detect speech
        - transcribe (stubbed)
        - ask OpenClaw (stubbed)
        - synthesize output (stubbed)

        This is intentionally a scaffold, not production behavior.
        """
        partial_text = []
        async for text_piece in self.stt.transcribe_stream(audio_chunks):
            partial_text.append(text_piece)

        text_prompt = " ".join(partial_text).strip() or "(no transcript)"
        agent_reply = await self.bridge.ask(text_prompt, session_id=session_id)

        async for out in self.tts.synthesize_stream(agent_reply):
            yield out
