import time

import pytest

from ralleh_voice.auth_tokens import (
    AuthTokenError,
    mint_signed_session_token,
    verify_signed_session_token,
)


def test_signed_token_roundtrip():
    now = int(time.time())
    token = mint_signed_session_token(
        session_id="sess-1",
        client="browser",
        key="dummy-signing-key",
        ttl_seconds=30,
        now=now,
        issuer="ralleh",
        audience="voice",
    )

    claims = verify_signed_session_token(
        token,
        key="dummy-signing-key",
        now=now,
        issuer="ralleh",
        audience="voice",
    )

    assert claims.sid == "sess-1"
    assert claims.clt == "browser"
    assert claims.iat == now
    assert claims.exp == now + 30


def test_signed_token_expired():
    token = mint_signed_session_token(
        session_id="sess-1",
        client="browser",
        key="dummy-signing-key",
        ttl_seconds=1,
        now=100,
    )

    with pytest.raises(AuthTokenError) as exc:
        verify_signed_session_token(token, key="dummy-signing-key", now=200, leeway_seconds=0)

    assert exc.value.reason == "expired"


def test_signed_token_tampered_bad_signature():
    token = mint_signed_session_token(
        session_id="sess-1",
        client="browser",
        key="dummy-signing-key",
        ttl_seconds=60,
        now=100,
    )
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.AAAA"

    with pytest.raises(AuthTokenError) as exc:
        verify_signed_session_token(tampered, key="dummy-signing-key", now=120)

    assert exc.value.reason == "bad_signature"


def test_signed_token_missing():
    with pytest.raises(AuthTokenError) as exc:
        verify_signed_session_token("", key="dummy-signing-key")

    assert exc.value.reason == "missing_token"


def test_signed_token_invalid_claim_redaction_safe():
    token = mint_signed_session_token(
        session_id="sess-1",
        client="browser",
        key="dummy-signing-key",
        ttl_seconds=60,
        now=100,
        issuer="issuer-A",
    )

    with pytest.raises(AuthTokenError) as exc:
        verify_signed_session_token(token, key="dummy-signing-key", now=120, issuer="issuer-B")

    assert exc.value.reason == "invalid_claim"
    assert "dummy-signing-key" not in exc.value.detail
