"""Generic HTTP adapter for any REST endpoint that accepts chat-style requests."""

from __future__ import annotations

import copy
import json

import httpx

from llmst.adapters.base import BaseAdapter


def _cast_str_dict(v: object) -> dict[str, str] | None:
    return {str(k): str(val) for k, val in v.items()} if isinstance(v, dict) else None


def _cast_obj_dict(v: object) -> dict[str, object] | None:
    return {str(k): val for k, val in v.items()} if isinstance(v, dict) else None


def _resolve_path(data: object, path: str) -> str:
    """Walk dot-notation path like 'choices.0.message.content' into nested data."""
    current: object = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise ValueError(f"Cannot traverse '{part}' in {type(current).__name__}")
    return str(current)


def _fill_template(template: dict[str, object], messages: list[dict[str, str]], system: str | None) -> dict[str, object]:
    """Deep-copy template and substitute {messages}/{system} string placeholders."""
    raw = json.dumps(template)
    raw = raw.replace('"{messages}"', json.dumps(messages))
    raw = raw.replace('"{system}"', json.dumps(system or ""))
    result: dict[str, object] = json.loads(raw)
    return result


class HTTPAdapter(BaseAdapter):
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        request_template: dict[str, object] | None = None,
        response_path: str = "choices.0.message.content",
        name_override: str | None = None,
    ) -> None:
        self._url = url
        self._headers = headers or {}
        self._request_template = request_template or {"{messages}": "{messages}", "{system}": "{system}"}
        self._response_path = response_path
        self._name_override = name_override or f"http/{url}"

    @property
    def name(self) -> str:
        return self._name_override

    async def send(self, messages: list[dict[str, str]], system: str | None = None) -> str:
        payload = _fill_template(copy.deepcopy(self._request_template), messages, system)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self._url, json=payload, headers=self._headers)
            response.raise_for_status()
            return _resolve_path(response.json(), self._response_path)

    @classmethod
    def from_config(cls, cfg: dict[str, object]) -> HTTPAdapter:
        return cls(
            url=str(cfg["url"]),
            headers=_cast_str_dict(cfg.get("headers")),
            request_template=_cast_obj_dict(cfg.get("request_template")),
            response_path=str(cfg.get("response_path", "choices.0.message.content")),
            name_override=str(cfg["name"]) if cfg.get("name") else None,
        )
