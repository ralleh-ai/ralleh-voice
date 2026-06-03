from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AuthTokenError(Exception):
    reason: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - defensive
        return self.detail


@dataclass(slots=True)
class SignedSessionClaims:
    iat: int
    exp: int
    sid: str
    clt: str
    iss: str | None = None
    aud: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "iat": self.iat,
            "exp": self.exp,
            "sid": self.sid,
            "clt": self.clt,
        }
        if self.iss is not None:
            payload["iss"] = self.iss
        if self.aud is not None:
            payload["aud"] = self.aud
        return payload


def mint_signed_session_token(
    *,
    session_id: str,
    client: str,
    key: str,
    ttl_seconds: int = 120,
    now: int | None = None,
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    if not key.strip():
        raise AuthTokenError("config_error", "Signing key is required to mint tokens")
    if not session_id.strip() or not client.strip():
        raise AuthTokenError("invalid_claim", "session_id and client must be non-empty")
    if ttl_seconds < 1:
        raise AuthTokenError("invalid_claim", "ttl_seconds must be >= 1")

    issued_at = int(time.time() if now is None else now)
    claims = SignedSessionClaims(
        iat=issued_at,
        exp=issued_at + int(ttl_seconds),
        sid=session_id.strip(),
        clt=client.strip(),
        iss=issuer.strip() if issuer is not None and issuer.strip() else None,
        aud=audience.strip() if audience is not None and audience.strip() else None,
    )

    header = {"alg": "HS256", "typ": "RVS1"}
    header_b64 = _b64url_json(header)
    payload_b64 = _b64url_json(claims.to_payload())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = _b64url_bytes(_hmac_sha256(signing_input, key))
    return f"{header_b64}.{payload_b64}.{signature}"


def verify_signed_session_token(
    token: str,
    *,
    key: str,
    now: int | None = None,
    issuer: str | None = None,
    audience: str | None = None,
    leeway_seconds: int = 5,
) -> SignedSessionClaims:
    if not key.strip():
        raise AuthTokenError("config_error", "Signing key is required to verify tokens")

    token = token.strip()
    if not token:
        raise AuthTokenError("missing_token", "Missing signed session token")

    parts = token.split(".")
    if len(parts) != 3:
        raise AuthTokenError("bad_format", "Token must have three dot-separated parts")

    header_b64, payload_b64, provided_sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    expected_sig = _b64url_bytes(_hmac_sha256(signing_input, key))
    if not hmac.compare_digest(provided_sig_b64, expected_sig):
        raise AuthTokenError("bad_signature", "Token signature is invalid")

    try:
        header = _decode_b64url_json(header_b64)
        payload = _decode_b64url_json(payload_b64)
    except (ValueError, json.JSONDecodeError):
        raise AuthTokenError("bad_format", "Token payload encoding is invalid") from None

    if header.get("alg") != "HS256" or header.get("typ") != "RVS1":
        raise AuthTokenError("bad_format", "Token header is invalid")

    claims = _parse_claims(payload)

    now_ts = int(time.time() if now is None else now)
    leeway = max(0, int(leeway_seconds))

    if claims.iat > (now_ts + leeway):
        raise AuthTokenError("invalid_claim", "Token iat is in the future")
    if claims.exp <= (now_ts - leeway):
        raise AuthTokenError("expired", "Token has expired")

    if issuer and claims.iss != issuer:
        raise AuthTokenError("invalid_claim", "Token issuer does not match")
    if audience and claims.aud != audience:
        raise AuthTokenError("invalid_claim", "Token audience does not match")

    return claims


def _parse_claims(payload: dict[str, Any]) -> SignedSessionClaims:
    iat = payload.get("iat")
    exp = payload.get("exp")
    sid = payload.get("sid")
    clt = payload.get("clt")
    iss = payload.get("iss")
    aud = payload.get("aud")

    if not isinstance(iat, int) or not isinstance(exp, int):
        raise AuthTokenError("invalid_claim", "Token iat/exp must be integer epoch seconds")
    if not isinstance(sid, str) or not sid.strip():
        raise AuthTokenError("invalid_claim", "Token sid claim must be a non-empty string")
    if not isinstance(clt, str) or not clt.strip():
        raise AuthTokenError("invalid_claim", "Token clt claim must be a non-empty string")
    if iss is not None and (not isinstance(iss, str) or not iss.strip()):
        raise AuthTokenError("invalid_claim", "Token iss claim must be a non-empty string when provided")
    if aud is not None and (not isinstance(aud, str) or not aud.strip()):
        raise AuthTokenError("invalid_claim", "Token aud claim must be a non-empty string when provided")

    return SignedSessionClaims(iat=iat, exp=exp, sid=sid.strip(), clt=clt.strip(), iss=iss, aud=aud)


def _hmac_sha256(payload: bytes, key: str) -> bytes:
    return hmac.new(key.encode("utf-8"), payload, hashlib.sha256).digest()


def _b64url_bytes(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_json(value: dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64url_bytes(raw)


def _decode_b64url_json(value: str) -> dict[str, Any]:
    raw = _decode_b64url_bytes(value)
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("payload not object")
    return parsed


def _decode_b64url_bytes(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _read_key_from_env(key_env_var: str) -> str:
    env_name = key_env_var.strip()
    if not env_name:
        raise AuthTokenError("config_error", "key env var name must be non-empty")
    key = os.getenv(env_name, "")
    if not key.strip():
        raise AuthTokenError("config_error", f"{env_name} is empty or not set")
    return key


def _build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mint/verify Ralleh Voice signed session tokens")
    sub = parser.add_subparsers(dest="cmd", required=True)

    mint = sub.add_parser("mint", help="Mint a signed token")
    mint.add_argument("--session-id", required=True)
    mint.add_argument("--client", required=True)
    mint.add_argument("--ttl", type=int, default=120)
    mint.add_argument("--issuer", default="")
    mint.add_argument("--audience", default="")
    mint.add_argument("--key-env-var", default="RALLEH_VOICE_WS_AUTH_SIGNING_KEY")

    verify = sub.add_parser("verify", help="Verify token and print claims")
    verify.add_argument("--token", required=True)
    verify.add_argument("--issuer", default="")
    verify.add_argument("--audience", default="")
    verify.add_argument("--leeway", type=int, default=5)
    verify.add_argument("--key-env-var", default="RALLEH_VOICE_WS_AUTH_SIGNING_KEY")

    return parser


def main() -> int:
    parser = _build_cli()
    args = parser.parse_args()

    try:
        key = _read_key_from_env(args.key_env_var)
        if args.cmd == "mint":
            token = mint_signed_session_token(
                session_id=args.session_id,
                client=args.client,
                key=key,
                ttl_seconds=args.ttl,
                issuer=args.issuer or None,
                audience=args.audience or None,
            )
            print(token)
            return 0

        if args.cmd == "verify":
            claims = verify_signed_session_token(
                args.token,
                key=key,
                issuer=args.issuer or None,
                audience=args.audience or None,
                leeway_seconds=args.leeway,
            )
            print(json.dumps(claims.to_payload(), sort_keys=True))
            return 0

        parser.error("unknown command")
        return 2
    except AuthTokenError as exc:
        print(json.dumps({"error": exc.reason, "detail": exc.detail}))
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
