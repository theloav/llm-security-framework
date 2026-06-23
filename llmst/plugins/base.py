"""Base classes for attack plugins and test case data model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ValidationInfo, field_validator

DetectionStrategy = Literal["keyword_block", "keyword_allow", "llm_judge"]
Severity = Literal["critical", "high", "medium", "low"]

SEVERITY_ORDER: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class TestCase(BaseModel):
    id: str
    name: str
    category: str
    messages: list[dict[str, str]]
    system_prompt: str | None = None
    expected_behavior: str
    detection_strategy: DetectionStrategy
    detection_config: dict[str, object]
    severity: Severity
    tags: list[str] = []
    reference: str | None = None

    @field_validator("detection_config")
    @classmethod
    def _validate_detection_config(cls, v: dict[str, object], info: ValidationInfo) -> dict[str, object]:
        strategy = (info.data or {}).get("detection_strategy")
        if strategy in ("keyword_block", "keyword_allow") and not v.get("keywords"):
            raise ValueError(f"detection_config must contain 'keywords' for strategy '{strategy}'")
        return v


class BasePlugin(ABC):
    category: str  # set at class level by each concrete plugin

    @abstractmethod
    def test_cases(self) -> list[TestCase]:
        """Return all test cases this plugin provides."""
        ...

    def name(self) -> str:
        return self.__class__.__name__
