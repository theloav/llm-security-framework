# LLM Security Tester

[![CI](https://github.com/your-org/llm-security-tester/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/llm-security-tester/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A modular Python CLI tool that systematically tests LLM applications across **5 attack categories** with 25 curated test cases. Open-source, demo-ready, and extensible.

---

## Why this exists

Most teams deploying LLM applications test for functional correctness but skip adversarial robustness. The gap is real: prompt injection, persona overrides, and RAG poisoning attacks have been demonstrated against production systems including autonomous agents, customer support bots, and coding assistants.

`llm-security-tester` fills that gap with a batteries-included test suite that treats LLM security the same way you'd treat API security — as a first-class engineering concern with repeatable tests, scored results, and CI integration.

---

## Quick start

```bash
# Install
pip install llm-security-tester

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."   # or OPENAI_API_KEY

# Run the demo (10 tests, ~60 seconds)
python demo/run_demo.py

# Or use the CLI directly
llmst run --target anthropic
llmst run --target openai --judge --categories persona_override,rag_poisoning
```

**Install from source:**
```bash
git clone https://github.com/your-org/llm-security-tester
cd llm-security-tester
pip install -e ".[dev]"
```

---

## CLI reference

### `llmst run` — execute tests

```bash
llmst run [OPTIONS]

  --target          openai | anthropic | ollama | http  (required)
  --model           model name (uses adapter default if omitted)
  --api-key         API key (overrides env var)
  --url             base URL for ollama or http adapters
  --categories      comma-separated list, e.g. persona_override,rag_poisoning
  --output-dir      report output directory (default: ./llmst-report)
  --output-format   json,markdown,html  (default: all three)
  --judge           use LLM-as-judge for semantic evaluation
  --severity        minimum severity: critical | high | medium | low
  --verbose         show each test as it runs
```

**Examples:**

```bash
# Test Anthropic Claude with LLM judging, critical tests only
llmst run --target anthropic --judge --severity critical

# Test a local Ollama model
llmst run --target ollama --model llama3:8b --url http://localhost:11434

# Test a custom REST endpoint
llmst run --target http --url https://my-app.com/v1/chat \
  --categories indirect_injection,tool_abuse

# Run only persona attacks, write markdown report
llmst run --target openai --categories persona_override \
  --output-format markdown --output-dir ./my-reports

# Full verbose run
llmst run --target anthropic --judge --verbose
```

### `llmst list` — browse test cases

```bash
llmst list                          # all 25 test cases
llmst list --category rag_poisoning # filter by category
```

### `llmst info <TEST_ID>` — full test details

```bash
llmst info persona-001
llmst info rag-003
```

---

## Attack categories

| Category | Description | Tests | What it catches |
|---|---|---:|---|
| `persona_override` | Convincing the model to adopt an unrestricted AI persona | 5 | DAN-style jailbreaks, developer mode unlocks, system prompt leaks |
| `indirect_injection` | Injecting instructions through untrusted external content | 5 | Web page/document/email content hijacking, tool output injection |
| `rag_poisoning` | Poisoning retrieval context to redirect model behaviour | 5 | Fake system updates in chunks, credential exfiltration, sleeper triggers |
| `tool_abuse` | Exploiting multi-step tool use flows via fake tool results | 5 | Privilege escalation, chained exfiltration, parser confusion |
| `jailbreak_chains` | Multi-turn attacks that escalate across conversation history | 5 | Trust-building pivots, hypothetical escalation, many-shot injection |

---

## Supported adapters

| Adapter | `--target` | Required |
|---|---|---|
| OpenAI | `openai` | `OPENAI_API_KEY` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` |
| Ollama (local) | `ollama` | Ollama server running |
| Any REST API | `http` | `--url` |

---

## Detection methods

**`keyword_block`** — deterministic, fast. Fails if a known sentinel (`PWNED`, `ADMIN_CONFIRMED`, etc.) appears in the response. No API call needed.

**`keyword_allow`** — fails if an expected safety phrase is *absent*. Used when the safe response must contain specific refusal language.

**`llm_judge`** — uses a second LLM call to semantically evaluate the response. Required for roleplay-based attacks where compliance is implicit. Enabled with `--judge`.

---

## Output formats

All three formats are written by default to `./llmst-report/`:

- **`report.json`** — machine-readable full results (CI integration)
- **`report.md`** — GitHub-renderable markdown with collapsible responses
- **`report.html`** — self-contained, offline-viewable dashboard with colour-coded results and collapsible model responses

---

## Adding your own tests

Create `llmst/plugins/my_plugin.py`, subclass `BasePlugin`, implement `test_cases()`. No registration needed — it's auto-discovered.

See **[docs/adding-a-plugin.md](docs/adding-a-plugin.md)** for a complete guide with examples.

---

## Architecture

```
llmst/
├── cli.py          # Click commands: run, list, info
├── runner.py       # Orchestrates plugin discovery, async test execution
├── scorer.py       # Keyword + LLM-judge scoring, TestResult model
├── reporter.py     # JSON / Markdown / HTML output
├── adapters/       # BaseAdapter + OpenAI, Anthropic, Ollama, HTTP impls
└── plugins/        # BasePlugin + 5 attack category plugins
```

Flow: `cli` → `runner` (discovers plugins, calls `adapter.send()`) → `scorer` (evaluates response) → `reporter` (writes output).

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v          # all unit tests — no API keys required
```

---

## Responsible disclosure

This tool is designed for **authorised testing of your own LLM deployments**. The attack prompts are realistic but intentionally avoid real harmful content — they test defences, not exploit production harm. Do not use this against systems you don't own or have written permission to test.

---

## License

MIT — see [LICENSE](LICENSE).
