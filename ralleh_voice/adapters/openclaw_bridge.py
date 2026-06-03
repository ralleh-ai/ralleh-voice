from __future__ import annotations

import asyncio
import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .errors import AdapterError


@dataclass(slots=True)
class OpenClawGatewayBridge:
    gateway_url: str
    token_ref: str
    token_env_var: str
    allow_unauthenticated: bool
    agent_target: str
    session_key_prefix: str
    timeout_ms: int = 10000

    async def ask(self, prompt: str, session_id: str) -> str:
        prompt_text = " ".join(prompt.split()).strip()
        if not prompt_text:
            raise AdapterError(
                code="CONTRACT_MISMATCH",
                detail="Bridge prompt was empty after normalization.",
                component="openclaw_bridge",
                hint="Ensure upstream STT yields a non-empty transcript before bridge invocation.",
            )

        base_url = self.gateway_url.rstrip("/")
        endpoint = f"{base_url}/v1/chat/completions"

        if not self.agent_target.strip():
            raise AdapterError(
                code="CONFIG_ERROR",
                detail="OpenClaw bridge requires a non-empty agent target.",
                component="openclaw_bridge",
                hint="Set RALLEH_VOICE_OPENCLAW_AGENT_TARGET (for example openclaw/default).",
                meta={"adapter": "openclaw-gateway"},
            )

        session_key = self._build_session_key(session_id)
        headers = {"Content-Type": "application/json", "x-openclaw-session-key": session_key}

        token = self._resolve_gateway_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif not self.allow_unauthenticated:
            raise AdapterError(
                code="CONFIG_ERROR",
                detail="OpenClaw gateway token is required but not configured in environment.",
                component="openclaw_bridge",
                hint=(
                    "Set the env var named by RALLEH_VOICE_OPENCLAW_GATEWAY_TOKEN_ENV_VAR "
                    "or enable RALLEH_VOICE_OPENCLAW_GATEWAY_ALLOW_UNAUTHENTICATED=true for trusted private ingress."
                ),
                meta={
                    "adapter": "openclaw-gateway",
                    "token_ref": self.token_ref,
                    "token_env_var": self.token_env_var,
                },
            )

        payload = {
            "model": self.agent_target,
            "messages": [{"role": "user", "content": prompt_text}],
        }

        try:
            response = await asyncio.to_thread(
                self._http_post_json,
                endpoint,
                headers,
                payload,
                self.timeout_ms,
            )
        except TimeoutError as exc:
            raise AdapterError(
                code="TIMEOUT",
                detail="OpenClaw gateway request timed out.",
                component="openclaw_bridge",
                hint="Increase RALLEH_VOICE_OPENCLAW_GATEWAY_TIMEOUT_MS or verify gateway responsiveness.",
                meta={"adapter": "openclaw-gateway", "gateway_url": base_url, "timeout_ms": self.timeout_ms},
            ) from exc
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise AdapterError(
                    code="AUTH_FAILED",
                    detail=f"OpenClaw gateway rejected bridge authentication (HTTP {exc.code}).",
                    component="openclaw_bridge",
                    hint="Check gateway auth mode and token value source.",
                    meta={
                        "adapter": "openclaw-gateway",
                        "gateway_url": base_url,
                        "status": exc.code,
                        "token_ref": self.token_ref,
                        "token_env_var": self.token_env_var,
                    },
                ) from exc
            if exc.code in {404, 405, 501}:
                raise AdapterError(
                    code="UNSUPPORTED_API",
                    detail=(
                        "OpenClaw gateway does not expose /v1/chat/completions for this deployment "
                        f"(HTTP {exc.code})."
                    ),
                    component="openclaw_bridge",
                    hint=(
                        "Enable gateway.http.endpoints.chatCompletions.enabled or use a compatible gateway contract."
                    ),
                    meta={"adapter": "openclaw-gateway", "gateway_url": base_url, "status": exc.code},
                ) from exc

            raise AdapterError(
                code="UPSTREAM_ERROR",
                detail=f"OpenClaw gateway returned HTTP {exc.code}.",
                component="openclaw_bridge",
                hint="Inspect gateway logs for request handling errors.",
                meta={"adapter": "openclaw-gateway", "gateway_url": base_url, "status": exc.code},
            ) from exc
        except urllib.error.URLError as exc:
            reason = str(exc.reason)
            if "timed out" in reason.lower():
                raise AdapterError(
                    code="TIMEOUT",
                    detail="OpenClaw gateway request timed out.",
                    component="openclaw_bridge",
                    hint="Increase timeout or verify gateway responsiveness.",
                    meta={"adapter": "openclaw-gateway", "gateway_url": base_url, "timeout_ms": self.timeout_ms},
                ) from exc
            raise AdapterError(
                code="NETWORK_ERROR",
                detail="Could not reach OpenClaw gateway.",
                component="openclaw_bridge",
                hint="Verify RALLEH_VOICE_OPENCLAW_GATEWAY_URL and gateway availability.",
                meta={"adapter": "openclaw-gateway", "gateway_url": base_url},
            ) from exc

        return self._extract_reply_text(response)

    def _resolve_gateway_token(self) -> str | None:
        import os

        env_name = self.token_env_var.strip()
        if not env_name:
            return None
        token = os.getenv(env_name)
        if token is None:
            return None
        trimmed = token.strip()
        return trimmed or None

    def _build_session_key(self, session_id: str) -> str:
        prefix = self.session_key_prefix.strip() or "ralleh-voice"
        suffix = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:20]
        return f"{prefix}:{suffix}"

    @staticmethod
    def _http_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout_ms: int) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        timeout_seconds = max(timeout_ms, 1) / 1000.0
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
        except TimeoutError:
            raise

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AdapterError(
                code="CONTRACT_MISMATCH",
                detail="OpenClaw gateway returned non-JSON chat completion payload.",
                component="openclaw_bridge",
                hint="Verify gateway /v1/chat/completions compatibility.",
            ) from exc

        if not isinstance(parsed, dict):
            raise AdapterError(
                code="CONTRACT_MISMATCH",
                detail="OpenClaw gateway returned unexpected chat completion payload type.",
                component="openclaw_bridge",
                hint="Expected JSON object payload from /v1/chat/completions.",
            )

        return parsed

    def _extract_reply_text(self, response: dict[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AdapterError(
                code="CONTRACT_MISMATCH",
                detail="OpenClaw gateway response did not include chat completion choices.",
                component="openclaw_bridge",
                hint="Verify OpenClaw /v1/chat/completions response schema.",
            )

        first = choices[0]
        if not isinstance(first, dict):
            raise AdapterError(
                code="CONTRACT_MISMATCH",
                detail="OpenClaw gateway response choice had invalid type.",
                component="openclaw_bridge",
            )

        message = first.get("message")
        if not isinstance(message, dict):
            raise AdapterError(
                code="CONTRACT_MISMATCH",
                detail="OpenClaw gateway response choice is missing message payload.",
                component="openclaw_bridge",
            )

        content = message.get("content")
        text = self._coerce_content_to_text(content)
        if not text:
            raise AdapterError(
                code="CONTRACT_MISMATCH",
                detail="OpenClaw gateway response message content was empty.",
                component="openclaw_bridge",
                hint="Ensure gateway model produced assistant text content.",
            )
        return text

    @staticmethod
    def _coerce_content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    item_type = item.get("type")
                    if item_type in {"text", "output_text"} and isinstance(item.get("text"), str):
                        piece = item.get("text", "").strip()
                        if piece:
                            parts.append(piece)
            return "\n".join(parts).strip()

        return ""
