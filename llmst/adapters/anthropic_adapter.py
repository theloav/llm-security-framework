"""Anthropic adapter — wraps the official async client."""

from __future__ import annotations

import os

from llmst.adapters.base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    def __init__(self, model: str = "claude-haiku-4-5-20251001", api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    @property
    def name(self) -> str:
        return f"anthropic/{self._model}"

    async def send(self, messages: list[dict[str, str]], system: str | None = None) -> str:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError("anthropic package is required: pip install anthropic") from e

        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        if system:
            response = await client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=messages,  # type: ignore[arg-type]
                system=system,
            )
        else:
            response = await client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=messages,  # type: ignore[arg-type]
            )
        block = response.content[0]
        return block.text if hasattr(block, "text") else str(block)

    @classmethod
    def from_config(cls, cfg: dict[str, object]) -> AnthropicAdapter:
        return cls(
            model=str(cfg.get("model", "claude-haiku-4-5-20251001")),
            api_key=str(cfg["api_key"]) if cfg.get("api_key") else None,
        )
