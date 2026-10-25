import argparse
import csv
import json
import os
import sys

from .core import build_tree, load, stats

ICONS = {"agent": "[A]", "llm": "[L]", "tool": "[T]", "retrieval": "[R]", "step": "[.]"}


def _print(node, depth, t0):
    a = node.get("attrs", {})
    extra = []
    if a.get("model"):
        extra.append(a["model"])
    if a.get("cost_usd"):
        extra.append(f"${a['cost_usd']:.4f}")
    if node.get("status") == "error":
        extra.append(f"ERROR {node.get('error', '')}")
    offset = (node["start"] - t0) * 1000
    print(
        f"{'  ' * depth}{ICONS.get(node['kind'], '[.]')} {node['name']:<{max(1, 40 - 2 * depth)}} +{offset:8.1f}ms {node.get('duration_ms', 0):9.1f}ms  {' '.join(extra)}"
    )
    for c in node["children"]:
        _print(c, depth + 1, t0)


def build_parser():
    ap = argparse.ArgumentParser(prog="agent-tracer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("tree", "stats"):
        p = sub.add_parser(name)
        p.add_argument("file")
        p.add_argument("--json", action="store_true")
    return ap


def _run(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    spans = load(a.file)
    if a.cmd == "tree":
        for trace_id, roots in build_tree(spans).items():
            print(f"trace {trace_id}")
            for r in roots:
                _print(r, 1, r["start"])
        return 0
    st = stats(spans)
    if a.json:
        print(json.dumps(st, indent=2))
        return 0
    print(
        f"{st['spans']} spans | errors {st['errors']} ({st['error_rate']:.1%}) | tokens {st['tokens']:,} | cost ${st['cost_usd']:.4f}"
    )
    for k, v in st["by_kind"].items():
        print(f"  {k:<10} {v['count']:>5} spans {v['ms']:>10.1f} ms")
    print("slowest: " + ", ".join(f"{n} ({ms:.0f}ms)" for n, ms in st["slowest"]))
    return 0


def main(argv=None):
    """Run the CLI; a bad input file or argument exits 2 with a one-line error instead of a traceback.

    Set AGENT_ECONOMY_DEBUG=1 to see the full traceback.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        return _run(argv)
    except (OSError, ValueError, KeyError, csv.Error) as e:
        if os.environ.get("AGENT_ECONOMY_DEBUG"):
            raise
        msg = e.args[0] if isinstance(e, KeyError) and e.args else e
        print(f"error: {msg}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
