"""Lightweight agent tracing SDK."""
from __future__ import annotations

import contextvars
import functools
import json
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager

__all__ = ["Tracer", "MODEL_PRICES", "load", "build_tree", "stats"]

# USD per million tokens (input, output) — placeholder price table, edit to taste.
MODEL_PRICES = {
    "claude-opus": (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (0.8, 4.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
}

_current = contextvars.ContextVar("agent_tracer_span", default=None)


def _price(model, tin, tout):
    if not model:
        return 0.0
    for name, (pi, po) in MODEL_PRICES.items():
        if model.startswith(name):
            return (tin or 0) / 1e6 * pi + (tout or 0) / 1e6 * po
    return 0.0


class Tracer:
    def __init__(self, path: str | None = None):
        self.path = path
        self.spans: list[dict] = []

    def _emit(self, span: dict):
        self.spans.append(span)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(span, default=str) + "\n")

    @contextmanager
    def span(self, name: str, kind: str = "step", **attrs):
        parent = _current.get()
        span = {
            "trace_id": parent["trace_id"] if parent else uuid.uuid4().hex,
            "span_id": uuid.uuid4().hex[:16],
            "parent_id": parent["span_id"] if parent else None,
            "name": name,
            "kind": kind,
            "start": time.time(),
            "attrs": dict(attrs),
            "status": "ok",
        }
        token = _current.set(span)
        try:
            yield span
        except Exception as e:
            span["status"] = "error"
            span["error"] = f"{type(e).__name__}: {e}"
            raise
        finally:
            _current.reset(token)
            span["end"] = time.time()
            span["duration_ms"] = round((span["end"] - span["start"]) * 1000, 3)
            a = span["attrs"]
            if "cost_usd" not in a and a.get("model"):
                a["cost_usd"] = round(_price(a["model"], a.get("input_tokens"), a.get("output_tokens")), 6)
            self._emit(span)

    def trace(self, name: str | None = None, kind: str = "step"):
        def deco(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                with self.span(name or fn.__name__, kind=kind):
                    return fn(*args, **kwargs)
            return wrapper
        return deco


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def build_tree(spans: list[dict]) -> dict[str, list[dict]]:
    """Return {trace_id: [root spans with nested 'children']} ordered by start time."""
    by_id = {s["span_id"]: {**s, "children": []} for s in spans}
    roots = defaultdict(list)
    for s in sorted(by_id.values(), key=lambda s: s["start"]):
        parent = by_id.get(s["parent_id"]) if s["parent_id"] else None
        (parent["children"] if parent else roots[s["trace_id"]]).append(s)
    return dict(roots)


def stats(spans: list[dict]) -> dict:
    out = {"spans": len(spans), "errors": 0, "cost_usd": 0.0, "tokens": 0,
           "by_kind": defaultdict(lambda: {"count": 0, "ms": 0.0}), "by_name": defaultdict(lambda: {"count": 0, "ms": 0.0, "errors": 0})}
    for s in spans:
        a = s.get("attrs", {})
        out["cost_usd"] += a.get("cost_usd", 0) or 0
        out["tokens"] += (a.get("input_tokens") or 0) + (a.get("output_tokens") or 0)
        err = s.get("status") == "error"
        out["errors"] += err
        k = out["by_kind"][s["kind"]]
        k["count"] += 1
        k["ms"] += s.get("duration_ms", 0)
        n = out["by_name"][s["name"]]
        n["count"] += 1
        n["ms"] += s.get("duration_ms", 0)
        n["errors"] += err
    out["error_rate"] = out["errors"] / len(spans) if spans else 0
    out["slowest"] = [(s["name"], s.get("duration_ms", 0)) for s in sorted(spans, key=lambda s: -s.get("duration_ms", 0))[:5]]
    out["by_kind"] = dict(out["by_kind"])
    out["by_name"] = dict(out["by_name"])
    return out
