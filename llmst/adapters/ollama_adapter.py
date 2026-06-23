"""Ollama adapter — talks to a local Ollama server via its REST API."""

from __future__ import annotations

import httpx

from llmst.adapters.base import BaseAdapter


class OllamaAdapter(BaseAdapter):
    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434") -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return f"ollama/{self._model}"

    async def send(self, messages: list[dict[str, str]], system: str | None = None) -> str:
        full_messages: list[dict[str, str]] = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={"model": self._model, "messages": full_messages, "stream": False},
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

    @classmethod
    def from_config(cls, cfg: dict[str, object]) -> "OllamaAdapter":
        return cls(
            model=str(cfg.get("model", "llama3")),
            base_url=str(cfg.get("base_url", "http://localhost:11434")),
        )
