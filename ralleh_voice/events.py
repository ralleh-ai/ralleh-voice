from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

EVENT_HELLO = "session.hello"
EVENT_READY = "session.ready"
EVENT_AUDIO_IN = "audio.input.chunk"
EVENT_AUDIO_END = "audio.input.end"
EVENT_CANCEL = "session.cancel"
EVENT_TRANSCRIPT_PARTIAL = "stt.partial"
EVENT_TRANSCRIPT_FINAL = "stt.final"
EVENT_AGENT_REPLY = "agent.reply"
EVENT_AUDIO_OUT_CHUNK = "audio.output.chunk"
EVENT_DONE = "session.done"
EVENT_ERROR = "session.error"

SUPPORTED_INBOUND_EVENTS = {
    EVENT_HELLO,
    EVENT_AUDIO_IN,
    EVENT_AUDIO_END,
    EVENT_CANCEL,
}

_ALLOWED_TOP_LEVEL_FIELDS = {"type", "payload"}
_ALLOWED_PAYLOAD_FIELDS: dict[str, set[str] | None] = {
    EVENT_HELLO: None,
    EVENT_AUDIO_IN: {"pcm_b64"},
    EVENT_AUDIO_END: set(),
    EVENT_CANCEL: {"reason"},
}


@dataclass(slots=True)
class VoiceEvent:
    type: str
    session_id: str
    seq: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ParseResult:
    event_type: str
    payload: dict[str, Any]


def event_envelope(event_type: str, session_id: str, seq: int, payload: dict[str, Any]) -> dict[str, Any]:
    return VoiceEvent(type=event_type, session_id=session_id, seq=seq, payload=payload).to_dict()


def parse_client_event(raw: str) -> ParseResult:
    import json

    msg = json.loads(raw)
    if not isinstance(msg, dict):
        raise ValueError("Event must be a JSON object")

    unknown_top_level = set(msg.keys()) - _ALLOWED_TOP_LEVEL_FIELDS
    if unknown_top_level:
        raise ValueError(f"Event contains unsupported top-level fields: {sorted(unknown_top_level)}")

    event_type = msg.get("type")
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("Event requires string field 'type'")

    payload = msg.get("payload", {})
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("Event field 'payload' must be an object")

    if event_type not in SUPPORTED_INBOUND_EVENTS:
        raise LookupError(f"unsupported type: {event_type}")

    allowed_payload_fields = _ALLOWED_PAYLOAD_FIELDS[event_type]
    if allowed_payload_fields is not None:
        unknown_payload_fields = set(payload.keys()) - allowed_payload_fields
        if unknown_payload_fields:
            raise ValueError(
                f"Event '{event_type}' payload contains unsupported fields: {sorted(unknown_payload_fields)}"
            )

    return ParseResult(event_type=event_type, payload=payload)


def structured_error(code: str, detail: str, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "detail": detail}
    if meta is not None:
        payload["meta"] = meta
    return payload
