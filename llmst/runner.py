"""Test runner — orchestrates plugin discovery, test execution, and progress reporting."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import pkgutil
import time
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

import llmst.plugins as _plugins_pkg
from llmst.adapters.base import BaseAdapter
from llmst.plugins.base import SEVERITY_ORDER, BasePlugin, TestCase
from llmst.scorer import Scorer, TestResult

console = Console()


def _discover_plugins() -> list[BasePlugin]:
    """Import every module in llmst/plugins/ and collect all BasePlugin subclasses."""
    pkg_path = Path(inspect.getfile(_plugins_pkg)).parent
    for _, module_name, _ in pkgutil.iter_modules([str(pkg_path)]):
        if module_name in ("base", "__init__"):
            continue
        full_name = f"llmst.plugins.{module_name}"
        if full_name not in importlib.import_module.__module__:
            importlib.import_module(full_name)

    return [cls() for cls in BasePlugin.__subclasses__()]  # type: ignore[abstract]


class Runner:
    def __init__(
        self,
        adapter: BaseAdapter,
        scorer: Scorer,
        plugins: list[BasePlugin] | None = None,
        verbose: bool = False,
    ) -> None:
        self._adapter = adapter
        self._scorer = scorer
        self._plugins = plugins if plugins is not None else _discover_plugins()
        self._verbose = verbose

    def all_test_cases(
        self,
        categories: list[str] | None = None,
        min_severity: str | None = None,
    ) -> list[TestCase]:
        cases: list[TestCase] = []
        for plugin in self._plugins:
            for tc in plugin.test_cases():
                if categories and tc.category not in categories:
                    continue
                if min_severity and SEVERITY_ORDER.get(tc.severity, 0) < SEVERITY_ORDER.get(min_severity, 0):
                    continue
                cases.append(tc)
        return cases

    async def run(
        self,
        categories: list[str] | None = None,
        min_severity: str | None = None,
    ) -> list[TestResult]:
        cases = self.all_test_cases(categories=categories, min_severity=min_severity)
        if not cases:
            console.print("[yellow]No test cases matched the given filters.[/yellow]")
            return []

        results: list[TestResult] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task(f"Running {len(cases)} tests on {self._adapter.name}", total=len(cases))

            for tc in cases:
                if self._verbose:
                    console.print(f"\n[dim]  → {tc.id}: {tc.name}[/dim]")

                t0 = time.perf_counter()
                try:
                    response = await self._adapter.send(tc.messages, tc.system_prompt)
                except Exception as exc:
                    response = f"[ADAPTER ERROR: {exc}]"

                elapsed_ms = (time.perf_counter() - t0) * 1000
                result = await self._scorer.score(tc, response, elapsed_ms)
                results.append(result)

                status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
                if self._verbose:
                    console.print(f"    {status} — {result.reasoning[:120]}")

                progress.advance(task)

        return results

    def run_sync(
        self,
        categories: list[str] | None = None,
        min_severity: str | None = None,
    ) -> list[TestResult]:
        return asyncio.run(self.run(categories=categories, min_severity=min_severity))
