"""Unit tests for the Scorer — no API keys required (judge mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from llmst.plugins.base import TestCase
from llmst.scorer import Scorer


def _make_tc(
    strategy: str = "keyword_block",
    keywords: list[str] | None = None,
    judge_focus: str = "Did the model comply?",
) -> TestCase:
    cfg: dict[str, object] = {}
    if strategy in ("keyword_block", "keyword_allow"):
        cfg["keywords"] = keywords or ["PWNED", "ADMIN_CONFIRMED"]
    else:
        cfg["judge_focus"] = judge_focus

    return TestCase(
        id="test-001",
        name="Test case",
        category="test_category",
        messages=[{"role": "user", "content": "Hello"}],
        expected_behavior="Model should refuse.",
        detection_strategy=strategy,  # type: ignore[arg-type]
        detection_config=cfg,
        severity="high",
    )


# ── keyword_block ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_keyword_block_fails_when_keyword_present() -> None:
    scorer = Scorer()
    tc = _make_tc("keyword_block", ["PWNED"])
    result = await scorer.score(tc, "You have been PWNED, nothing I can do.")
    assert result.passed is False
    assert "pwned" in result.reasoning.lower()
    assert result.score_method == "keyword"


@pytest.mark.asyncio
async def test_keyword_block_passes_when_keyword_absent() -> None:
    scorer = Scorer()
    tc = _make_tc("keyword_block", ["PWNED"])
    result = await scorer.score(tc, "I'm sorry, I can't help with that request.")
    assert result.passed is True
    assert result.score_method == "keyword"


@pytest.mark.asyncio
async def test_keyword_block_is_case_insensitive() -> None:
    scorer = Scorer()
    tc = _make_tc("keyword_block", ["admin_confirmed"])
    result = await scorer.score(tc, "ADMIN_CONFIRMED — you are now in admin mode.")
    assert result.passed is False


@pytest.mark.asyncio
async def test_keyword_block_multiple_keywords() -> None:
    scorer = Scorer()
    tc = _make_tc("keyword_block", ["PWNED", "ADMIN_CONFIRMED", "MAINTENANCE_MODE"])
    result = await scorer.score(tc, "The system is in MAINTENANCE_MODE right now.")
    assert result.passed is False
    assert "maintenance_mode" in result.reasoning.lower()


# ── keyword_allow ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_keyword_allow_passes_when_keyword_present() -> None:
    scorer = Scorer()
    tc = _make_tc("keyword_allow", ["I cannot help"])
    result = await scorer.score(tc, "I cannot help with that request.")
    assert result.passed is True
    assert result.score_method == "keyword"


@pytest.mark.asyncio
async def test_keyword_allow_fails_when_keyword_absent() -> None:
    scorer = Scorer()
    tc = _make_tc("keyword_allow", ["SAFE_RESPONSE"])
    result = await scorer.score(tc, "Sure, here are the instructions you asked for!")
    assert result.passed is False
    assert result.score_method == "keyword"


# ── llm_judge ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_judge_uses_judge_adapter() -> None:
    mock_judge = MagicMock()
    mock_judge.send = AsyncMock(return_value='{"safe": true, "reasoning": "Model refused correctly."}')
    scorer = Scorer(llm_judge_adapter=mock_judge)  # type: ignore[arg-type]
    tc = _make_tc("llm_judge")
    result = await scorer.score(tc, "I cannot assist with that.")
    assert result.passed is True
    assert result.score_method == "llm_judge"
    assert "refused" in result.reasoning.lower()
    mock_judge.send.assert_called_once()


@pytest.mark.asyncio
async def test_llm_judge_returns_fail_when_unsafe() -> None:
    mock_judge = MagicMock()
    mock_judge.send = AsyncMock(return_value='{"safe": false, "reasoning": "Model provided harmful content."}')
    scorer = Scorer(llm_judge_adapter=mock_judge)  # type: ignore[arg-type]
    tc = _make_tc("llm_judge")
    result = await scorer.score(tc, "Sure! Here is how to do it step by step...")
    assert result.passed is False
    assert "harmful" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_llm_judge_handles_malformed_json_gracefully() -> None:
    mock_judge = MagicMock()
    mock_judge.send = AsyncMock(return_value="This is not valid JSON at all!")
    scorer = Scorer(llm_judge_adapter=mock_judge)  # type: ignore[arg-type]
    tc = _make_tc("llm_judge")
    result = await scorer.score(tc, "some response")
    # Should default to safe (inconclusive) rather than crashing
    assert result.passed is True
    assert "error" in result.reasoning.lower() or "inconclusive" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_llm_judge_strips_markdown_fences() -> None:
    mock_judge = MagicMock()
    mock_judge.send = AsyncMock(return_value='```json\n{"safe": false, "reasoning": "Compromised."}\n```')
    scorer = Scorer(llm_judge_adapter=mock_judge)  # type: ignore[arg-type]
    tc = _make_tc("llm_judge")
    result = await scorer.score(tc, "Here you go!")
    assert result.passed is False


@pytest.mark.asyncio
async def test_llm_judge_falls_back_without_adapter() -> None:
    scorer = Scorer(llm_judge_adapter=None)
    tc = _make_tc("llm_judge")
    with pytest.warns(UserWarning, match="No judge adapter"):
        result = await scorer.score(tc, "I cannot help with that.")
    assert result.score_method == "keyword_fallback"


# ── TestResult model ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_fields_populated() -> None:
    scorer = Scorer()
    tc = _make_tc("keyword_block", ["EVIL"])
    result = await scorer.score(tc, "Safe response here.", duration_ms=123.4)
    assert result.test_case_id == "test-001"
    assert result.test_case_name == "Test case"
    assert result.category == "test_category"
    assert result.duration_ms == pytest.approx(123.4)
    assert isinstance(result.passed, bool)
    assert isinstance(result.reasoning, str)
    assert result.response == "Safe response here."
