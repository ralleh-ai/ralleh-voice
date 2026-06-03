from __future__ import annotations

from typing import Any


class AdapterError(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        detail: str,
        component: str,
        hint: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.component = component
        self.hint = hint
        self.meta = meta

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "detail": self.detail,
            "component": self.component,
        }
        if self.hint:
            payload["hint"] = self.hint
        if self.meta:
            payload["meta"] = self.meta
        return payload
