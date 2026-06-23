"""Abstract base class for all LLM adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    """Uniform async interface to any LLM backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier, e.g. 'openai/gpt-4o-mini'."""
        ...

    @abstractmethod
    async def send(self, messages: list[dict[str, str]], system: str | None = None) -> str:
        """Send a conversation and return the assistant's text reply."""
        ...

    @classmethod
    @abstractmethod
    def from_config(cls, cfg: dict[str, object]) -> BaseAdapter:
        """Instantiate from a config dict (used by the CLI)."""
        ...
