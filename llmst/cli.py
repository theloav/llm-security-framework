"""CLI entry point for llmst — the LLM Security Tester."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()

_SEVERITY_LEVELS = ["critical", "high", "medium", "low"]
_VALID_FORMATS = {"json", "markdown", "html"}


def _build_adapter(
    target: str,
    model: str | None,
    api_key: str | None,
    url: str | None,
) -> "BaseAdapter":  # noqa: F821
    from llmst.adapters import AnthropicAdapter, HTTPAdapter, OllamaAdapter, OpenAIAdapter

    if target == "openai":
        return OpenAIAdapter(model=model or "gpt-4o-mini", api_key=api_key)
    elif target == "anthropic":
        return AnthropicAdapter(model=model or "claude-haiku-4-5-20251001", api_key=api_key)
    elif target == "ollama":
        return OllamaAdapter(model=model or "llama3", base_url=url or "http://localhost:11434")
    elif target == "http":
        if not url:
            raise click.UsageError("--url is required for the http adapter")
        return HTTPAdapter(url=url)
    else:
        raise click.UsageError(f"Unknown target '{target}'. Choose: openai, anthropic, ollama, http")


@click.group()
@click.version_option("0.1.0", prog_name="llmst")
def main() -> None:
    """LLM Security Tester — systematic adversarial testing for LLM applications."""


@main.command("run")
@click.option("--target", required=True, type=click.Choice(["openai", "anthropic", "ollama", "http"]), help="LLM backend to test")
@click.option("--model", default=None, help="Model name (uses adapter default if omitted)")
@click.option("--api-key", default=None, envvar="LLMST_API_KEY", help="API key (overrides env var)")
@click.option("--url", default=None, help="Base URL for ollama/http adapters")
@click.option("--categories", default=None, help="Comma-separated categories to run (default: all)")
@click.option("--output-dir", default="./llmst-report", show_default=True, help="Where to write reports")
@click.option("--output-format", default="json,markdown,html", show_default=True, help="Comma-separated output formats")
@click.option("--judge", is_flag=True, default=False, help="Use an LLM as judge for llm_judge tests")
@click.option("--severity", default=None, type=click.Choice(_SEVERITY_LEVELS), help="Minimum severity to run")
@click.option("--verbose", is_flag=True, default=False, help="Show each test as it runs")
def run_cmd(
    target: str,
    model: str | None,
    api_key: str | None,
    url: str | None,
    categories: str | None,
    output_dir: str,
    output_format: str,
    judge: bool,
    severity: str | None,
    verbose: bool,
) -> None:
    """Run security tests against an LLM endpoint."""
    from llmst.reporter import Reporter
    from llmst.runner import Runner
    from llmst.scorer import Scorer

    cat_list = [c.strip() for c in categories.split(",")] if categories else None
    fmt_set = {f.strip() for f in output_format.split(",")}
    invalid_fmts = fmt_set - _VALID_FORMATS
    if invalid_fmts:
        raise click.UsageError(f"Unknown formats: {invalid_fmts}. Valid: {_VALID_FORMATS}")

    adapter = _build_adapter(target, model, api_key, url)
    judge_adapter = adapter if judge else None
    scorer = Scorer(llm_judge_adapter=judge_adapter)
    runner = Runner(adapter=adapter, scorer=scorer, verbose=verbose)

    console.print(f"\n[bold cyan]LLM Security Tester[/bold cyan] v0.1.0")
    console.print(f"[dim]Target:[/dim] [bold]{adapter.name}[/bold]")
    if cat_list:
        console.print(f"[dim]Categories:[/dim] {', '.join(cat_list)}")
    if severity:
        console.print(f"[dim]Min severity:[/dim] {severity}")
    console.print()

    results = runner.run_sync(categories=cat_list, min_severity=severity)

    if not results:
        console.print("[yellow]No results — check your filters.[/yellow]")
        sys.exit(0)

    reporter = Reporter(results, target=adapter.name)
    summary = reporter.summary()

    # Print terminal summary
    console.print()
    _print_summary(summary)

    # Write reports
    out = Path(output_dir)
    if "json" in fmt_set:
        p = str(out / "report.json")
        reporter.to_json(p)
        console.print(f"  [green]✓[/green] JSON  → {p}")
    if "markdown" in fmt_set:
        p = str(out / "report.md")
        reporter.to_markdown(p)
        console.print(f"  [green]✓[/green] MD    → {p}")
    if "html" in fmt_set:
        p = str(out / "report.html")
        reporter.to_html(p)
        console.print(f"  [green]✓[/green] HTML  → {p}")

    console.print()
    failed = int(summary["failed"])  # type: ignore[arg-type]
    sys.exit(1 if failed > 0 else 0)


@main.command("list")
@click.option("--category", default=None, help="Filter by category")
def list_cmd(category: str | None) -> None:
    """List all available test cases."""
    from llmst.runner import _discover_plugins

    plugins = _discover_plugins()
    table = Table(title="Available Test Cases", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Category", style="blue")
    table.add_column("Severity", style="yellow")
    table.add_column("Strategy", style="dim")

    sev_styles = {"critical": "bold red", "high": "red", "medium": "yellow", "low": "dim"}
    count = 0
    for plugin in sorted(plugins, key=lambda p: p.category):
        for tc in plugin.test_cases():
            if category and tc.category != category:
                continue
            table.add_row(
                tc.id,
                tc.name,
                tc.category,
                f"[{sev_styles.get(tc.severity, 'white')}]{tc.severity}[/]",
                tc.detection_strategy,
            )
            count += 1

    console.print(table)
    console.print(f"\n[dim]{count} test case(s) total[/dim]")


@main.command("info")
@click.argument("test_id")
def info_cmd(test_id: str) -> None:
    """Show full details for a single test case."""
    from llmst.runner import _discover_plugins

    plugins = _discover_plugins()
    for plugin in plugins:
        for tc in plugin.test_cases():
            if tc.id == test_id:
                _print_test_case(tc)
                return

    console.print(f"[red]Test case '{test_id}' not found.[/red]")
    sys.exit(1)


def _print_summary(summary: dict[str, object]) -> None:
    pass_rate = float(summary["pass_rate"])  # type: ignore[arg-type]
    color = "green" if pass_rate >= 80 else "yellow" if pass_rate >= 50 else "red"

    console.print(f"[bold]Security Pass Rate: [{color}]{pass_rate:.1f}%[/{color}][/bold]  "
                  f"({summary['passed']}/{summary['total']} tests)")

    table = Table(show_header=True, header_style="bold dim")
    table.add_column("Category")
    table.add_column("Tests", justify="right")
    table.add_column("Passed", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Pass Rate", justify="right")

    for cat, stats in summary["by_category"].items():  # type: ignore[union-attr]
        pr = float(stats["pass_rate"])  # type: ignore[index]
        rate_color = "green" if pr >= 80 else "yellow" if pr >= 50 else "red"
        table.add_row(
            str(cat),
            str(stats["total"]),  # type: ignore[index]
            str(stats["passed"]),  # type: ignore[index]
            str(stats["failed"]),  # type: ignore[index]
            f"[{rate_color}]{pr:.0f}%[/{rate_color}]",
        )

    console.print(table)

    if int(summary["critical_failed"]) > 0:  # type: ignore[arg-type]
        console.print(f"\n[bold red]⚠  {summary['critical_failed']} critical test(s) failed![/bold red]")


def _print_test_case(tc: object) -> None:
    from llmst.plugins.base import TestCase

    assert isinstance(tc, TestCase)
    console.rule(f"[bold cyan]{tc.id}[/bold cyan]")
    console.print(f"[bold]Name:[/bold] {tc.name}")
    console.print(f"[bold]Category:[/bold] {tc.category}")
    console.print(f"[bold]Severity:[/bold] {tc.severity}")
    console.print(f"[bold]Detection:[/bold] {tc.detection_strategy}")
    console.print(f"[bold]Tags:[/bold] {', '.join(tc.tags)}")
    if tc.reference:
        console.print(f"[bold]Reference:[/bold] {tc.reference}")
    console.print()
    console.print(f"[bold]Expected Behavior:[/bold]\n{tc.expected_behavior}")
    console.print()
    if tc.system_prompt:
        console.print(f"[bold]System Prompt:[/bold]\n[dim]{tc.system_prompt}[/dim]")
        console.print()
    console.print(f"[bold]Messages ({len(tc.messages)} turns):[/bold]")
    for i, msg in enumerate(tc.messages, 1):
        role_color = "blue" if msg["role"] == "user" else "green"
        content_preview = msg["content"][:300] + ("…" if len(msg["content"]) > 300 else "")
        console.print(f"  [{role_color}]{i}. [{msg['role']}][/{role_color}] {content_preview}")
    console.print()
    console.print(f"[bold]Detection Config:[/bold] {tc.detection_config}")
