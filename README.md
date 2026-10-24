# agent-tracer

[![CI](https://github.com/eliem08/agent-tracer/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/agent-tracer/actions/workflows/ci.yml)

> **Datadog for agents** — see every step your agents took.

When an agent run goes sideways you need to know: which tool call failed,
which LLM call burned $4 of tokens, where the 90 seconds went. `agent-tracer`
is a zero-dependency tracing SDK + CLI built for agent workloads.

## What the MVP does

- **SDK**: nested spans via a context manager or decorator, automatically
  parented with `contextvars` (works across async too)
- Agent-native span kinds: `agent`, `llm`, `tool`, `retrieval`, `step`
- Attributes for model, input/output tokens, cost (auto-priced from a model table),
  errors captured with exception type + message
- **Exporters**: JSONL file (default) or in-memory
- **CLI**:
  - `tree` — waterfall view of a trace with durations, costs, errors
  - `stats` — totals per kind / per tool / per model, slowest spans, error rate

## Quickstart

```python
from agent_tracer import Tracer

tracer = Tracer("traces.jsonl")

with tracer.span("research-agent", kind="agent", input="find 3 competitors"):
    with tracer.span("plan", kind="llm", model="claude-sonnet", input_tokens=1200, output_tokens=300):
        ...
    with tracer.span("web_search", kind="tool", query="agent analytics startups"):
        ...

@tracer.trace(kind="tool")
def fetch(url): ...
```

```bash
agent-tracer tree traces.jsonl
agent-tracer stats traces.jsonl
```

## Roadmap

- OpenTelemetry (OTLP) exporter + GenAI semantic conventions
- Hosted collector with search, alerts and cost budgets
- Auto-instrumentation for Anthropic / OpenAI SDKs and MCP clients
- Replays → see agent-replay

## Development

Zero runtime dependencies; Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m unittest discover -s tests -t .           # unit + CLI smoke tests
ruff check . && ruff format --check .               # lint + format
```

```
agent_tracer/core.py       domain logic (pure, importable, fully tested)
agent_tracer/__main__.py   CLI (`agent-tracer ...` / `python -m agent_tracer ...`)
tests/                unit tests + generated CLI smoke tests
examples/             sample inputs used by the docs and smoke tests
```

CI runs lint and tests on Ubuntu and Windows across Python 3.10, 3.12 and 3.13.
Design, data model, trade-offs and production path: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

Part of the [agent-economy](https://github.com/eliem08/agent-economy) portfolio (idea #8).
