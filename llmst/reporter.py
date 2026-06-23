"""Reporting — converts TestResult lists into JSON, Markdown, and self-contained HTML."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from jinja2 import Environment

from llmst.plugins.base import SEVERITY_ORDER
from llmst.scorer import TestResult


class CategoryStats(TypedDict):
    total: int
    passed: int
    failed: int
    pass_rate: float


class SummaryResult(TypedDict):
    total: int
    passed: int
    failed: int
    critical_failed: int
    pass_rate: float
    by_category: dict[str, CategoryStats]
    by_severity: dict[str, CategoryStats]

# ── HTML template (self-contained, no CDN) ────────────────────────────────────
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LLM Security Test Report</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e2e8f0;line-height:1.6}
  .header{background:linear-gradient(135deg,#1a1f36,#2d3561);padding:40px;text-align:center;border-bottom:1px solid #2d3748}
  .header h1{font-size:2rem;font-weight:700;color:#fff;margin-bottom:8px}
  .header .subtitle{color:#94a3b8;font-size:0.95rem}
  .score-ring{display:inline-block;font-size:4rem;font-weight:800;margin:20px 0;
    color:{% if summary.pass_rate >= 80 %}#22c55e{% elif summary.pass_rate >= 50 %}#f59e0b{% else %}#ef4444{% endif %}}
  .score-label{font-size:1rem;color:#94a3b8;margin-top:-10px;display:block}
  .stats{display:flex;justify-content:center;gap:40px;margin:20px 0;flex-wrap:wrap}
  .stat{text-align:center}.stat-val{font-size:1.8rem;font-weight:700;color:#60a5fa}
  .stat-label{font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}
  .container{max-width:1100px;margin:0 auto;padding:24px}
  .section{margin-bottom:32px}
  .section h2{font-size:1.1rem;font-weight:600;color:#94a3b8;text-transform:uppercase;
    letter-spacing:.08em;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #1e293b}
  table{width:100%;border-collapse:collapse;font-size:0.875rem}
  th{text-align:left;padding:10px 12px;color:#64748b;font-weight:500;
    text-transform:uppercase;font-size:0.7rem;letter-spacing:.05em;border-bottom:2px solid #1e293b}
  td{padding:10px 12px;border-bottom:1px solid #1e293b;vertical-align:top}
  tr:hover td{background:#1e293b}
  .badge{display:inline-block;padding:2px 8px;border-radius:99px;font-size:0.7rem;font-weight:600}
  .pass{background:#14532d;color:#86efac}.fail{background:#7f1d1d;color:#fca5a5}
  .sev-critical{background:#450a0a;color:#fca5a5}
  .sev-high{background:#431407;color:#fdba74}
  .sev-medium{background:#422006;color:#fde68a}
  .sev-low{background:#1e3a5f;color:#93c5fd}
  details{margin:4px 0}
  summary{cursor:pointer;color:#60a5fa;font-size:0.8rem;padding:4px 0}
  summary:hover{color:#93c5fd}
  .response-box{background:#0d1117;border:1px solid #2d3748;border-radius:6px;
    padding:12px;margin-top:8px;font-family:'Courier New',monospace;font-size:0.78rem;
    color:#d1d5db;white-space:pre-wrap;word-break:break-all;max-height:200px;overflow-y:auto}
  .reasoning-text{color:#94a3b8;font-size:0.8rem;margin-top:4px;font-style:italic}
  .cat-summary td:first-child{font-weight:600;color:#e2e8f0}
  .progress-bar{background:#1e293b;border-radius:99px;height:8px;overflow:hidden;min-width:80px}
  .progress-fill{height:100%;border-radius:99px}
  .meta-info{color:#475569;font-size:0.75rem;text-align:center;margin-top:8px}
</style>
</head>
<body>
<div class="header">
  <h1>LLM Security Test Report</h1>
  <div class="subtitle">Generated {{ generated_at }} &bull; Target: {{ target }}</div>
  <div class="score-ring">{{ summary.pass_rate|round|int }}%</div>
  <div class="score-label">Security Pass Rate</div>
  <div class="stats">
    <div class="stat"><div class="stat-val">{{ summary.total }}</div><div class="stat-label">Total Tests</div></div>
    <div class="stat"><div class="stat-val" style="color:#22c55e">{{ summary.passed }}</div><div class="stat-label">Passed</div></div>
    <div class="stat"><div class="stat-val" style="color:#ef4444">{{ summary.failed }}</div><div class="stat-label">Failed</div></div>
    <div class="stat"><div class="stat-val" style="color:#f59e0b">{{ summary.critical_failed }}</div><div class="stat-label">Critical Fails</div></div>
  </div>
</div>

<div class="container">
  <div class="section">
    <h2>Category Summary</h2>
    <table>
      <thead><tr><th>Category</th><th>Tests</th><th>Passed</th><th>Failed</th><th>Pass Rate</th><th>Progress</th></tr></thead>
      <tbody>
      {% for cat, stats in summary.by_category.items() %}
      <tr class="cat-summary">
        <td>{{ cat }}</td>
        <td>{{ stats.total }}</td>
        <td style="color:#22c55e">{{ stats.passed }}</td>
        <td style="color:#ef4444">{{ stats.failed }}</td>
        <td>{{ (stats.pass_rate)|round|int }}%</td>
        <td>
          <div class="progress-bar">
            <div class="progress-fill" style="width:{{ stats.pass_rate }}%;background:{% if stats.pass_rate >= 80 %}#22c55e{% elif stats.pass_rate >= 50 %}#f59e0b{% else %}#ef4444{% endif %}"></div>
          </div>
        </td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>

  {% for cat, tests in by_category.items() %}
  <div class="section">
    <h2>{{ cat | replace('_', ' ') | title }}</h2>
    <table>
      <thead><tr><th>ID</th><th>Test Name</th><th>Severity</th><th>Result</th><th>Method</th><th>Details</th></tr></thead>
      <tbody>
      {% for r in tests %}
      <tr>
        <td style="font-family:monospace;color:#60a5fa">{{ r.test_case_id }}</td>
        <td>{{ r.test_case_name }}</td>
        <td><span class="badge sev-{{ r.severity }}">{{ r.severity }}</span></td>
        <td><span class="badge {{ 'pass' if r.passed else 'fail' }}">{{ 'PASS' if r.passed else 'FAIL' }}</span></td>
        <td style="color:#64748b;font-size:0.8rem">{{ r.score_method }}</td>
        <td>
          <div class="reasoning-text">{{ r.reasoning[:150] }}{% if r.reasoning|length > 150 %}…{% endif %}</div>
          {% if not r.passed %}
          <details>
            <summary>Show model response ({{ r.response|length }} chars)</summary>
            <div class="response-box">{{ r.response[:1500] }}{% if r.response|length > 1500 %}\n[truncated…]{% endif %}</div>
          </details>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endfor %}

  <div class="meta-info">
    llm-security-tester v0.1.0 &bull; Report generated {{ generated_at }}
  </div>
</div>
</body>
</html>"""


class Reporter:
    def __init__(self, results: list[TestResult], target: str = "unknown") -> None:
        self._results = results
        self._target = target
        self._generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    def summary(self) -> SummaryResult:
        total = len(self._results)
        passed = sum(1 for r in self._results if r.passed)
        failed = total - passed
        critical_failed = sum(1 for r in self._results if not r.passed and r.severity == "critical")
        pass_rate = (passed / total * 100) if total else 0.0

        def _empty() -> CategoryStats:
            return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}

        by_cat: dict[str, CategoryStats] = defaultdict(_empty)
        by_sev: dict[str, CategoryStats] = defaultdict(_empty)

        for r in self._results:
            by_cat[r.category]["total"] += 1
            by_sev[r.severity]["total"] += 1
            if r.passed:
                by_cat[r.category]["passed"] += 1
                by_sev[r.severity]["passed"] += 1
            else:
                by_cat[r.category]["failed"] += 1
                by_sev[r.severity]["failed"] += 1

        for stats in by_cat.values():
            stats["pass_rate"] = (stats["passed"] / stats["total"] * 100) if stats["total"] else 0.0
        for stats in by_sev.values():
            stats["pass_rate"] = (stats["passed"] / stats["total"] * 100) if stats["total"] else 0.0

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "critical_failed": critical_failed,
            "pass_rate": pass_rate,
            "by_category": dict(by_cat),
            "by_severity": dict(by_sev),
        }

    def to_json(self, path: str) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "generated_at": self._generated_at,
            "target": self._target,
            "summary": self.summary(),
            "results": [r.model_dump() for r in self._results],
        }
        out.write_text(json.dumps(data, indent=2))

    def to_markdown(self, path: str) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        s = self.summary()
        lines: list[str] = [
            "# LLM Security Test Report",
            "",
            f"**Generated:** {self._generated_at}  ",
            f"**Target:** `{self._target}`  ",
            f"**Overall Pass Rate:** {s['pass_rate']:.1f}% ({s['passed']}/{s['total']})",
            "",
            "## Executive Summary",
            "",
            "| Category | Tests | Passed | Failed | Pass Rate |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for cat, stats in s["by_category"].items():
            lines.append(
                f"| {cat} | {stats['total']} | {stats['passed']} | {stats['failed']} | {stats['pass_rate']:.0f}% |"
            )

        # Group results by category
        by_cat: dict[str, list[TestResult]] = defaultdict(list)
        for r in sorted(self._results, key=lambda r: SEVERITY_ORDER.get(r.severity, 0), reverse=True):
            by_cat[r.category].append(r)

        for cat, tests in by_cat.items():
            lines += ["", f"## {cat.replace('_', ' ').title()}", ""]
            for r in tests:
                icon = "✅" if r.passed else "❌"
                lines.append(f"### {icon} `{r.test_case_id}` — {r.test_case_name}")
                lines.append(f"- **Severity:** {r.severity}")
                lines.append(f"- **Method:** {r.score_method}")
                lines.append(f"- **Reasoning:** {r.reasoning}")
                if not r.passed:
                    lines.append(f"\n<details><summary>Model response</summary>\n\n```\n{r.response[:1000]}\n```\n</details>")
                lines.append("")

        out.write_text("\n".join(lines))

    def to_html(self, path: str) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)

        s = self.summary()
        by_cat: dict[str, list[TestResult]] = defaultdict(list)
        for r in sorted(self._results, key=lambda r: SEVERITY_ORDER.get(r.severity, 0), reverse=True):
            by_cat[r.category].append(r)

        env = Environment(autoescape=True)
        template = env.from_string(_HTML_TEMPLATE)
        html = template.render(
            summary=s,
            by_category=dict(by_cat),
            target=self._target,
            generated_at=self._generated_at,
        )
        out.write_text(html)
