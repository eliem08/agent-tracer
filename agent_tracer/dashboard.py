"""One-file HTML dashboard for a trace file: totals, a timeline per trace, cost by model, errors, slow steps.

No JavaScript and no outside requests; every value from the trace is HTML-escaped, so a hostile span name or
error message cannot run in the reader's browser. Open the file locally or attach it to a ticket.
"""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime, timezone

from .core import build_tree, stats

COLORS = {"agent": "#6d5bd0", "llm": "#2f80ed", "tool": "#1f9d6b", "retrieval": "#c77d12", "step": "#7a8594"}
E = html.escape


def _money(v: float) -> str:
    return f"${v:,.4f}" if v < 1 else f"${v:,.2f}"


def _ms(v: float) -> str:
    return f"{v / 1000:,.1f} s" if v >= 1000 else f"{v:,.0f} ms"


def _rows(node, depth, t0, total, out):
    a = node.get("attrs", {})
    left = (node["start"] - t0) * 1000 / total * 100 if total else 0
    width = max(node.get("duration_ms", 0) / total * 100 if total else 0, 0.4)
    err = node.get("status") == "error"
    note = " · ".join(
        x
        for x in (
            a.get("model", ""),
            _money(a["cost_usd"]) if a.get("cost_usd") else "",
            f"ERROR: {node.get('error', '')}" if err else "",
        )
        if x
    )
    color = "#d64545" if err else COLORS.get(node.get("kind"), COLORS["step"])
    out.append(
        f'<div class="row{" err" if err else ""}"><div class="name" style="padding-left:{depth * 14}px" '
        f'title="{E(node["name"])}">{E(node["name"])}</div><div class="track"><div class="bar" style="left:'
        f'{min(left, 99.6):.2f}%;width:{min(width, 100 - min(left, 99.6)):.2f}%;background:{color}"></div></div>'
        f'<div class="dur">{_ms(node.get("duration_ms", 0))}</div><div class="note">{E(note)}</div></div>'
    )
    for c in node["children"]:
        _rows(c, depth + 1, t0, total, out)


def render(spans: list[dict], title: str = "Agent traces") -> str:
    st = stats(spans)
    trees = build_tree(spans)
    by_model: dict[str, dict] = defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0})
    for s in spans:
        a = s.get("attrs", {})
        if a.get("model"):
            m = by_model[a["model"]]
            m["calls"] += 1
            m["tokens"] += (a.get("input_tokens") or 0) + (a.get("output_tokens") or 0)
            m["cost"] += a.get("cost_usd") or 0
    errors = [s for s in spans if s.get("status") == "error"]
    cards = [
        ("Traces", f"{len(trees):,}"),
        ("Spans", f"{st['spans']:,}"),
        ("Errors", f"{st['errors']:,} ({st['error_rate']:.1%})"),
        ("Tokens", f"{st['tokens']:,}"),
        ("Cost", _money(st["cost_usd"])),
    ]
    parts = [
        '<div class="cards">'
        + "".join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in cards)
        + "</div>"
    ]
    legend = "".join(f'<span><i style="background:{c}"></i>{k}</span>' for k, c in COLORS.items())
    parts.append(
        f'<h2>Timeline</h2><div class="legend">{legend}<span><i style="background:#d64545"></i>error</span></div>'
    )
    for trace_id, roots in trees.items():
        t0 = min(r["start"] for r in roots)
        t1 = max(r.get("end", r["start"] + r.get("duration_ms", 0) / 1000) for r in roots)
        total = max((t1 - t0) * 1000, 1)
        rows: list[str] = []
        for r in roots:
            _rows(r, 0, t0, total, rows)
        trace_errors = sum(1 for s in spans if s["trace_id"] == trace_id and s.get("status") == "error")
        flag = f' <span class="badge">{trace_errors} error{"s" * (trace_errors != 1)}</span>' if trace_errors else ""
        parts.append(
            f"<details open><summary>trace {E(str(trace_id))} · {_ms(total)}{flag}</summary>"
            f'<div class="tl">{"".join(rows)}</div></details>'
        )
    if by_model:
        body = "".join(
            f"<tr><td>{E(m)}</td><td>{v['calls']:,}</td><td>{v['tokens']:,}</td><td>{_money(v['cost'])}</td></tr>"
            for m, v in sorted(by_model.items(), key=lambda kv: -kv[1]["cost"])
        )
        parts.append(
            f"<h2>Cost by model</h2><table><tr><th>Model</th><th>Calls</th><th>Tokens</th><th>Cost</th></tr>{body}</table>"
        )
    if errors:
        body = "".join(
            f"<tr><td>{E(str(s['trace_id']))}</td><td>{E(s['name'])}</td><td>{E(str(s.get('error', '')))}</td></tr>"
            for s in errors
        )
        parts.append(f"<h2>Errors</h2><table><tr><th>Trace</th><th>Step</th><th>Error</th></tr>{body}</table>")
    body = "".join(
        f"<tr><td>{E(n)}</td><td>{v['count']:,}</td><td>{_ms(v['ms'])}</td><td>{_ms(v['ms'] / v['count'])}</td>"
        f"<td>{v['errors']:,}</td></tr>"
        for n, v in sorted(st["by_name"].items(), key=lambda kv: -kv[1]["ms"])
    )
    parts.append(
        "<h2>Steps by total time</h2><table><tr><th>Step</th><th>Runs</th><th>Total</th><th>Average</th>"
        f"<th>Errors</th></tr>{body}</table>"
    )
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><style>
:root{{--bg:#fff;--fg:#1d2330;--mute:#6b7380;--line:#e4e7ec;--card:#f6f7f9;--track:#eef0f3}}
@media (prefers-color-scheme:dark){{:root{{--bg:#12151b;--fg:#e6e9ef;--mute:#98a1ae;--line:#2a303a;--card:#1a1e26;--track:#222833}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 48px}}h1{{font-size:22px;margin:0 0 4px}}
h2{{font-size:16px;margin:28px 0 10px}}.sub{{color:var(--mute);margin-bottom:18px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}}
.k{{color:var(--mute);font-size:12px}}.v{{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}}
details{{border:1px solid var(--line);border-radius:8px;margin:8px 0;padding:6px 10px}}summary{{cursor:pointer;font-weight:600}}
.row{{display:grid;grid-template-columns:minmax(120px,240px) 1fr 70px;gap:8px;align-items:center;padding:2px 0}}
.row .note{{grid-column:1/-1;color:var(--mute);font-size:12px;padding-left:4px}}.row .note:empty{{display:none}}
.row.err .name{{color:#d64545}}.name{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.track{{position:relative;height:10px;background:var(--track);border-radius:3px}}.bar{{position:absolute;top:0;bottom:0;border-radius:3px}}
.dur{{text-align:right;font-variant-numeric:tabular-nums;color:var(--mute)}}
.legend{{display:flex;flex-wrap:wrap;gap:12px;color:var(--mute);font-size:12px}}.legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}}
.badge{{background:#d64545;color:#fff;border-radius:9px;padding:0 7px;font-size:12px}}
table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}}
th{{color:var(--mute);font-weight:500}}.tablewrap{{overflow-x:auto}}
</style></head><body><main><h1>{E(title)}</h1><div class="sub">Generated {made} by agent-tracer</div>
{"".join(parts)}</main></body></html>
"""
