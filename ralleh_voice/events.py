from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


EVENT_HELLO = "session.hello"
EVENT_READY = "session.ready"
EVENT_AUDIO_IN = "audio.input.chunk"
EVENT_BARGE_IN = "session.barge_in"
EVENT_CANCEL = "session.cancel"
EVENT_TRANSCRIPT_PARTIAL = "stt.partial"
EVENT_TRANSCRIPT_FINAL = "stt.final"
EVENT_AGENT_REPLY = "agent.reply"
EVENT_AUDIO_OUT_CHUNK = "audio.output.chunk"
EVENT_DONE = "session.done"
EVENT_ERROR = "session.error"


@dataclass(slots=True)
class VoiceEvent:
    type: str
    session_id: str
    seq: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def event_envelope(event_type: str, session_id: str, seq: int, payload: dict[str, Any]) -> dict[str, Any]:
    return VoiceEvent(type=event_type, session_id=session_id, seq=seq, payload=payload).to_dict()
