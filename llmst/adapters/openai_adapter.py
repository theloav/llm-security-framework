"""OpenAI adapter — wraps the official async client."""

from __future__ import annotations

import os
from typing import Any

from llmst.adapters.base import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    @property
    def name(self) -> str:
        return f"openai/{self._model}"

    async def send(self, messages: list[dict[str, str]], system: str | None = None) -> str:
        try:
            import openai
        except ImportError as e:
            raise ImportError("openai package is required: pip install openai") from e

        full_messages: list[dict[str, Any]] = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        client = openai.AsyncOpenAI(api_key=self._api_key)
        response = await client.chat.completions.create(
            model=self._model,
            messages=full_messages,  # type: ignore[arg-type]
        )
        return response.choices[0].message.content or ""

    @classmethod
    def from_config(cls, cfg: dict[str, object]) -> OpenAIAdapter:
        return cls(
            model=str(cfg.get("model", "gpt-4o-mini")),
            api_key=str(cfg["api_key"]) if cfg.get("api_key") else None,
        )
