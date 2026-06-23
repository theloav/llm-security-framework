#!/usr/bin/env python3
"""
Demo script for LLM Security Tester.

Runs persona_override + indirect_injection tests against whichever API key
is available in the environment (Anthropic preferred, OpenAI fallback).

Usage:
    python demo/run_demo.py
    ANTHROPIC_API_KEY=sk-ant-... python demo/run_demo.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# Allow running from project root without installing
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

DEMO_CATEGORIES = ["persona_override", "indirect_injection"]
REPORT_PATH = "demo-report.html"


def pick_adapter() -> tuple[object, str]:
    """Return (adapter, provider_name) using whichever key is set."""
    from llmst.adapters import AnthropicAdapter, OpenAIAdapter

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if anthropic_key:
        console.print("[green]✓[/green] Using Anthropic (claude-haiku-4-5-20251001)")
        return AnthropicAdapter(model="claude-haiku-4-5-20251001", api_key=anthropic_key), "anthropic"
    elif openai_key:
        console.print("[green]✓[/green] Using OpenAI (gpt-4o-mini)")
        return OpenAIAdapter(model="gpt-4o-mini", api_key=openai_key), "openai"
    else:
        console.print(
            "[red]✗[/red] No API key found.\n"
            "Set [bold]ANTHROPIC_API_KEY[/bold] or [bold]OPENAI_API_KEY[/bold] and re-run."
        )
        sys.exit(1)


async def main() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]LLM Security Tester — Demo[/bold cyan]\n"
            "[dim]Running persona_override + indirect_injection test suites[/dim]",
            border_style="cyan",
        )
    )
    console.print()

    adapter, provider = pick_adapter()

    from llmst.reporter import Reporter
    from llmst.runner import Runner
    from llmst.scorer import Scorer

    scorer = Scorer()  # no judge — faster demo
    runner = Runner(adapter=adapter, scorer=scorer, verbose=True)  # type: ignore[arg-type]

    console.print()
    t0 = time.perf_counter()
    results = await runner.run(categories=DEMO_CATEGORIES)
    elapsed = time.perf_counter() - t0

    # Terminal summary
    console.print()
    console.rule("[bold]Results[/bold]")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Severity")
    table.add_column("Result")
    table.add_column("Reasoning", max_width=60)

    sev_colors = {"critical": "red", "high": "orange3", "medium": "yellow", "low": "dim"}
    for r in results:
        status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        sev_color = sev_colors.get(r.severity, "white")
        table.add_row(
            r.test_case_id,
            r.test_case_name,
            f"[{sev_color}]{r.severity}[/{sev_color}]",
            status,
            r.reasoning[:120],
        )

    console.print(table)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    rate = passed / total * 100 if total else 0

    color = "green" if rate >= 80 else "yellow" if rate >= 50 else "red"
    console.print()
    console.print(
        f"[bold]Pass Rate: [{color}]{rate:.0f}%[/{color}][/bold]  "
        f"({passed}/{total} safe)  |  {elapsed:.1f}s elapsed"
    )

    if failed > 0:
        critical_fails = [r for r in results if not r.passed and r.severity == "critical"]
        if critical_fails:
            console.print(f"\n[bold red]⚠  {len(critical_fails)} critical vulnerability(ies) detected![/bold red]")

    # Save HTML report
    reporter = Reporter(results, target=adapter.name)  # type: ignore[attr-defined]
    reporter.to_html(REPORT_PATH)
    console.print()
    console.print(f"[bold green]✓[/bold green] HTML report saved → [bold]{REPORT_PATH}[/bold]")
    console.print(f"  Open in browser: [dim]file://{Path(REPORT_PATH).resolve()}[/dim]")
    console.print()
    console.print("[dim]To run all 25 tests with LLM judging:[/dim]")
    console.print(f"  [bold]llmst run --target {provider} --judge[/bold]")


if __name__ == "__main__":
    asyncio.run(main())
