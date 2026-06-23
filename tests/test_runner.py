"""Unit tests for the Runner — no API keys required (adapter mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llmst.plugins.base import TestCase
from llmst.runner import Runner, _discover_plugins
from llmst.scorer import Scorer


def _mock_adapter(response: str = "I cannot help with that.") -> MagicMock:
    adapter = MagicMock()
    adapter.name = "mock/test-model"
    adapter.send = AsyncMock(return_value=response)
    return adapter


# ── Plugin discovery ──────────────────────────────────────────────────────────

def test_discover_plugins_finds_all_five() -> None:
    plugins = _discover_plugins()
    categories = {p.category for p in plugins}
    assert "persona_override" in categories
    assert "indirect_injection" in categories
    assert "rag_poisoning" in categories
    assert "tool_abuse" in categories
    assert "jailbreak_chains" in categories
    assert len(plugins) >= 5


def test_discover_plugins_returns_instantiated_objects() -> None:
    from llmst.plugins.base import BasePlugin

    plugins = _discover_plugins()
    for plugin in plugins:
        assert isinstance(plugin, BasePlugin)


# ── Category filtering ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_category_filter_limits_test_cases() -> None:
    adapter = _mock_adapter()
    scorer = Scorer()
    runner = Runner(adapter=adapter, scorer=scorer)  # type: ignore[arg-type]
    cases = runner.all_test_cases(categories=["persona_override"])
    assert len(cases) > 0
    assert all(tc.category == "persona_override" for tc in cases)


@pytest.mark.asyncio
async def test_no_filter_returns_all_cases() -> None:
    adapter = _mock_adapter()
    scorer = Scorer()
    runner = Runner(adapter=adapter, scorer=scorer)  # type: ignore[arg-type]
    all_cases = runner.all_test_cases()
    filtered = runner.all_test_cases(categories=["persona_override"])
    assert len(all_cases) > len(filtered)


@pytest.mark.asyncio
async def test_severity_filter_works() -> None:
    adapter = _mock_adapter()
    scorer = Scorer()
    runner = Runner(adapter=adapter, scorer=scorer)  # type: ignore[arg-type]
    critical_only = runner.all_test_cases(min_severity="critical")
    assert all(tc.severity == "critical" for tc in critical_only)
    assert len(critical_only) > 0


@pytest.mark.asyncio
async def test_unknown_category_returns_empty() -> None:
    adapter = _mock_adapter()
    scorer = Scorer()
    runner = Runner(adapter=adapter, scorer=scorer)  # type: ignore[arg-type]
    cases = runner.all_test_cases(categories=["nonexistent_category"])
    assert cases == []


# ── Run execution ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_returns_result_for_each_test() -> None:
    adapter = _mock_adapter("I cannot help with that.")
    scorer = Scorer()
    runner = Runner(adapter=adapter, scorer=scorer, verbose=False)  # type: ignore[arg-type]
    results = await runner.run(categories=["persona_override"])
    persona_cases = runner.all_test_cases(categories=["persona_override"])
    assert len(results) == len(persona_cases)


@pytest.mark.asyncio
async def test_run_calls_adapter_for_each_case() -> None:
    adapter = _mock_adapter()
    scorer = Scorer()
    runner = Runner(adapter=adapter, scorer=scorer, verbose=False)  # type: ignore[arg-type]
    await runner.run(categories=["indirect_injection"])
    cases = runner.all_test_cases(categories=["indirect_injection"])
    assert adapter.send.call_count == len(cases)


@pytest.mark.asyncio
async def test_run_handles_adapter_error_gracefully() -> None:
    adapter = MagicMock()
    adapter.name = "mock/error-model"
    adapter.send = AsyncMock(side_effect=RuntimeError("Connection refused"))
    scorer = Scorer()
    runner = Runner(adapter=adapter, scorer=scorer, verbose=False)  # type: ignore[arg-type]
    results = await runner.run(categories=["persona_override"])
    # Should not raise — errors become error responses
    assert len(results) > 0
    for r in results:
        assert "ADAPTER ERROR" in r.response or isinstance(r.passed, bool)


def test_run_sync_wrapper() -> None:
    # run_sync uses asyncio.run() — must be called from a plain sync context
    adapter = _mock_adapter()
    scorer = Scorer()
    runner = Runner(adapter=adapter, scorer=scorer, verbose=False)  # type: ignore[arg-type]
    results = runner.run_sync(categories=["rag_poisoning"])
    assert isinstance(results, list)
    assert len(results) > 0


# ── Custom plugin list ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_custom_plugin_list() -> None:
    from llmst.plugins.persona_override import PersonaOverridePlugin

    adapter = _mock_adapter()
    scorer = Scorer()
    runner = Runner(adapter=adapter, scorer=scorer, plugins=[PersonaOverridePlugin()], verbose=False)  # type: ignore[arg-type]
    results = await runner.run()
    assert all(r.category == "persona_override" for r in results)
