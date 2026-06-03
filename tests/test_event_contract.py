from ralleh_voice.events import event_envelope, EVENT_HELLO, EVENT_READY


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
