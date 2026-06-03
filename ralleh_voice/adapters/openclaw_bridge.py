from __future__ import annotations

from dataclasses import dataclass

from .errors import AdapterError


@dataclass(slots=True)
class OpenClawGatewayBridge:
    gateway_url: str
    token_ref: str
    timeout_ms: int = 10000

    async def ask(self, prompt: str, session_id: str) -> str:
        _ = (prompt, session_id)
        raise AdapterError(
            code="MISSING_ENDPOINT",
            detail="OpenClaw bridge is not wired: no stable HTTP/WebSocket endpoint contract is pinned in this repo.",
            component="openclaw_bridge",
            hint="Pin an explicit OpenClaw gateway endpoint/method contract for this repository before enabling openclaw-gateway mode.",
            meta={
                "adapter": "openclaw-gateway",
                "gateway_url": self.gateway_url,
                "token_ref": self.token_ref,
                "evidence": {
                    "source": "local-openclaw-dist-inspection",
                    "observed": [
                        "Gateway RPC methods exist behind internal client protocol",
                        "No stable public REST endpoint pinned for session ask in this repo",
                    ],
                },
            },
        )
