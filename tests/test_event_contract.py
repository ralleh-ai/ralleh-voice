import json

import pytest

from ralleh_voice.events import (
    EVENT_AUDIO_END,
    EVENT_AUDIO_IN,
    EVENT_CANCEL,
    EVENT_HELLO,
    EVENT_READY,
    event_envelope,
    parse_client_event,
)


def test_event_envelope_contract():
    ev = event_envelope(EVENT_HELLO, "sess-1", 7, {"foo": "bar"})
    assert set(ev.keys()) == {"type", "session_id", "seq", "payload"}
    assert ev["type"] == EVENT_HELLO
    assert ev["session_id"] == "sess-1"
    assert ev["seq"] == 7
    assert ev["payload"]["foo"] == "bar"


def test_event_constants_present():
    assert EVENT_HELLO == "session.hello"
    assert EVENT_READY == "session.ready"
    assert EVENT_AUDIO_IN == "audio.input.chunk"
    assert EVENT_AUDIO_END == "audio.input.end"
    assert EVENT_CANCEL == "session.cancel"


def test_parse_client_event_valid():
    parsed = parse_client_event(json.dumps({"type": EVENT_HELLO, "payload": {"client": "browser"}}))
    assert parsed.event_type == EVENT_HELLO
    assert parsed.payload["client"] == "browser"


@pytest.mark.parametrize(
    "raw,error_type",
    [
        ("{", json.JSONDecodeError),
        (json.dumps(["not-object"]), ValueError),
        (json.dumps({"payload": {}}), ValueError),
        (json.dumps({"type": "", "payload": {}}), ValueError),
        (json.dumps({"type": "unsupported.event", "payload": {}}), LookupError),
        (json.dumps({"type": EVENT_AUDIO_IN, "payload": "nope"}), ValueError),
    ],
)
def test_parse_client_event_failures(raw, error_type):
    with pytest.raises(error_type):
        parse_client_event(raw)
