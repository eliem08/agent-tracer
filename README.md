<!-- sell-kit:start -->
# Agent Tracer

[![CI](https://github.com/eliem08/agent-tracer/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/agent-tracer/actions/workflows/ci.yml)

> **See every step your agents took, what it cost and where it broke.**

**Who it's for:** Teams running LLM agents in production.

**The problem:** When an agent fails or burns money, there is no trace of which step, tool or model call caused it.

**What you get:** A zero-dependency tracing SDK that records spans, cost, tokens and errors, with tree and stats views from the command line.

## Quickstart

Customers receive a release archive with the wheel and the examples. Python 3.10+ and no other dependencies.

```bash
pip install agent_tracer-0.1.0-py3-none-any.whl
agent-tracer tree examples/trace.jsonl
agent-tracer stats examples/trace.jsonl
agent-tracer tree examples/otlp-trace.json
```

## Web app and API

Every command is also a JSON API endpoint and a browser form, served by the built-in web app.

```bash
agent-tracer-web --port 8000          # then open http://127.0.0.1:8000
agent-tracer-web keys create --label "first customer"   # prints an API key (stored hashed)
docker build -t agent-tracer . && docker run -p 8000:8000 -e API_KEYS=sk_... -v agent-tracer-data:/data agent-tracer
```

Every API call needs `Authorization: Bearer <key>` once any key exists; a server on a public address refuses to start without one. Calls are rate-limited per key (60/min, `--rate`) and metered: `agent-tracer-web usage` prints calls per key for billing.

Endpoints: `POST /api/tree`, `POST /api/stats`, plus `GET /healthz` and `GET /api/spec` (machine-readable field list).
Files are sent as `{"name": ..., "content": ...}`, folders as `{"files": [...]}` or a base64 zip.

## Deploy and sell

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/eliem08/agent-tracer)

`render.yaml` (one click, above) and `fly.toml` (`fly launch --copy-config`) both run the Dockerfile with a persistent `/data` volume and a `/healthz` check.
To sell self-serve, set four variables and point a Stripe webhook at `https://<your-host>/billing/webhook` (events `checkout.session.completed` and `customer.subscription.deleted`):

| Variable | Example |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `STRIPE_PRICES` | `team=price_123,business=price_456` |
| `PUBLIC_URL` | `https://agent-tracer.example.com` |

Buyers pick a plan on `/pricing`, pay on Stripe Checkout and see their API key once on the success page. Cancelling the subscription revokes the key. A selling server always requires a key.

## Pricing

Every plan starts with a 14-day free trial. Prices in USD, billed monthly unless noted.

| Plan | Price | Includes |
|---|---|---|
| **Developer** | Free for 1 developer | Local tracing; Tree and stats views; Community support |
| **Team** | $99 per month | 10 developers; Cost and error dashboards; Trace export |
| **Business** | $499 per month | Unlimited developers; Retention controls; Priority support |

To start a trial or buy a plan, [request access](https://github.com/eliem08/agent-tracer/issues/new?title=Agent%20Tracer%20trial&labels=sales).

## Licence

Proprietary. Copyright (c) 2026 eliem08. All rights reserved. Use requires a paid plan or an active trial; see [LICENSE](LICENSE).
<!-- sell-kit:end -->

## What it does

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
