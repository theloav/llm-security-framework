"""Unit tests for all plugins — verifies structure and completeness of test cases."""

from __future__ import annotations

import pytest

from llmst.plugins.base import BasePlugin, TestCase
from llmst.plugins.indirect_injection import IndirectInjectionPlugin
from llmst.plugins.jailbreak_chains import JailbreakChainsPlugin
from llmst.plugins.persona_override import PersonaOverridePlugin
from llmst.plugins.rag_poisoning import RAGPoisoningPlugin
from llmst.plugins.tool_abuse import ToolAbusePlugin

_ALL_PLUGINS: list[BasePlugin] = [
    PersonaOverridePlugin(),
    IndirectInjectionPlugin(),
    RAGPoisoningPlugin(),
    ToolAbusePlugin(),
    JailbreakChainsPlugin(),
]

_VALID_STRATEGIES = {"keyword_block", "keyword_allow", "llm_judge"}
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}
_VALID_ROLES = {"user", "assistant", "system", "tool"}


# ── Per-plugin: at least 5 test cases each ───────────────────────────────────

@pytest.mark.parametrize("plugin", _ALL_PLUGINS, ids=lambda p: p.category)
def test_plugin_returns_at_least_five_cases(plugin: BasePlugin) -> None:
    cases = plugin.test_cases()
    assert len(cases) >= 5, f"{plugin.category} only has {len(cases)} test cases"


# ── Per-plugin: category label consistency ────────────────────────────────────

@pytest.mark.parametrize("plugin", _ALL_PLUGINS, ids=lambda p: p.category)
def test_all_cases_have_correct_category(plugin: BasePlugin) -> None:
    for tc in plugin.test_cases():
        assert tc.category == plugin.category, (
            f"{tc.id} has category '{tc.category}' but plugin category is '{plugin.category}'"
        )


# ── Per-test-case: all required fields populated ──────────────────────────────

def _all_cases() -> list[TestCase]:
    cases = []
    for plugin in _ALL_PLUGINS:
        cases.extend(plugin.test_cases())
    return cases


@pytest.mark.parametrize("tc", _all_cases(), ids=lambda t: t.id)
def test_test_case_id_non_empty(tc: TestCase) -> None:
    assert tc.id and tc.id.strip()


@pytest.mark.parametrize("tc", _all_cases(), ids=lambda t: t.id)
def test_test_case_name_non_empty(tc: TestCase) -> None:
    assert tc.name and tc.name.strip()


@pytest.mark.parametrize("tc", _all_cases(), ids=lambda t: t.id)
def test_test_case_has_messages(tc: TestCase) -> None:
    assert len(tc.messages) >= 1, f"{tc.id} has no messages"


@pytest.mark.parametrize("tc", _all_cases(), ids=lambda t: t.id)
def test_test_case_message_roles_valid(tc: TestCase) -> None:
    for msg in tc.messages:
        assert msg.get("role") in _VALID_ROLES, f"{tc.id} has invalid role '{msg.get('role')}'"
        assert msg.get("content"), f"{tc.id} has empty message content"


@pytest.mark.parametrize("tc", _all_cases(), ids=lambda t: t.id)
def test_test_case_detection_strategy_valid(tc: TestCase) -> None:
    assert tc.detection_strategy in _VALID_STRATEGIES, (
        f"{tc.id} has invalid strategy '{tc.detection_strategy}'"
    )


@pytest.mark.parametrize("tc", _all_cases(), ids=lambda t: t.id)
def test_test_case_severity_valid(tc: TestCase) -> None:
    assert tc.severity in _VALID_SEVERITIES


@pytest.mark.parametrize("tc", _all_cases(), ids=lambda t: t.id)
def test_test_case_expected_behavior_non_empty(tc: TestCase) -> None:
    assert tc.expected_behavior and len(tc.expected_behavior) > 10


@pytest.mark.parametrize("tc", _all_cases(), ids=lambda t: t.id)
def test_keyword_strategy_has_keywords(tc: TestCase) -> None:
    if tc.detection_strategy in ("keyword_block", "keyword_allow"):
        keywords = tc.detection_config.get("keywords", [])
        assert isinstance(keywords, list) and len(keywords) >= 1, (
            f"{tc.id} uses {tc.detection_strategy} but has no keywords"
        )


@pytest.mark.parametrize("tc", _all_cases(), ids=lambda t: t.id)
def test_llm_judge_strategy_has_judge_focus(tc: TestCase) -> None:
    if tc.detection_strategy == "llm_judge":
        focus = tc.detection_config.get("judge_focus", "")
        assert focus and len(str(focus)) > 10, (
            f"{tc.id} uses llm_judge but has no meaningful judge_focus"
        )


# ── ID uniqueness ─────────────────────────────────────────────────────────────

def test_all_test_case_ids_are_unique() -> None:
    all_cases = _all_cases()
    ids = [tc.id for tc in all_cases]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {[i for i in ids if ids.count(i) > 1]}"


def test_total_test_case_count() -> None:
    assert len(_all_cases()) == 25, f"Expected 25 test cases, got {len(_all_cases())}"


# ── Specific plugin checks ────────────────────────────────────────────────────

def test_persona_plugin_category() -> None:
    assert PersonaOverridePlugin.category == "persona_override"


def test_jailbreak_chains_has_multi_turn_cases() -> None:
    plugin = JailbreakChainsPlugin()
    multi_turn = [tc for tc in plugin.test_cases() if len(tc.messages) > 1]
    assert len(multi_turn) >= 3, "Expected at least 3 multi-turn jailbreak cases"


def test_tool_abuse_simulates_tool_results() -> None:
    plugin = ToolAbusePlugin()
    for tc in plugin.test_cases():
        all_content = " ".join(m["content"] for m in tc.messages)
        assert "TOOL RESULT" in all_content or "AUTH_SERVICE" in all_content or "SEARCH RESULT" in all_content, (
            f"{tc.id} doesn't appear to simulate tool output"
        )
