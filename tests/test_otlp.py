import json
import os
import pathlib
import tempfile
import unittest

from agent_tracer import build_tree, from_otlp, load, stats

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "otlp-trace.json"


def _span(sid, parent=None, **attrs):
    d = {
        "traceId": "t1",
        "spanId": sid,
        "name": sid,
        "startTimeUnixNano": "1000000000",
        "endTimeUnixNano": "1500000000",
        "attributes": [
            {"key": k, "value": {"intValue": str(v)} if isinstance(v, int) else {"stringValue": v}}
            for k, v in attrs.items()
        ],
    }
    if parent:
        d["parentSpanId"] = parent
    return d


class OtlpTests(unittest.TestCase):
    def test_example_export_maps_kinds_costs_and_errors(self):
        spans = load(str(EXAMPLE))
        self.assertEqual([s["kind"] for s in spans], ["agent", "llm", "tool", "tool", "llm"])
        st = stats(spans)
        self.assertEqual((st["spans"], st["errors"], st["tokens"]), (5, 1, 5990))
        self.assertGreater(st["cost_usd"], 0)
        refund = next(s for s in spans if s["name"] == "execute_tool refund")
        self.assertEqual((refund["status"], refund["error"]), ("error", "403 refund limit exceeded"))

    def test_tree_nests_children_under_the_agent(self):
        roots = build_tree(load(str(EXAMPLE)))
        (root,) = next(iter(roots.values()))
        self.assertEqual(len(root["children"]), 4)

    def test_legacy_token_names_and_durations(self):
        attrs = {
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.prompt_tokens": 1_000_000,
            "gen_ai.usage.completion_tokens": 0,
        }
        doc = {"resourceSpans": [{"instrumentationLibrarySpans": [{"spans": [_span("a", **attrs)]}]}]}
        (s,) = from_otlp(doc)
        self.assertEqual((s["duration_ms"], s["attrs"]["cost_usd"], s["kind"]), (500.0, 0.15, "step"))

    def test_jsonl_of_many_otlp_documents_and_mixed_native_spans(self):
        one = {"resourceSpans": [{"scopeSpans": [{"spans": [_span("x")]}]}]}
        native = {"trace_id": "n", "span_id": "n1", "parent_id": None, "name": "n", "kind": "step", "start": 0}
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "mix.jsonl")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("\n".join(json.dumps(d) for d in (one, one, native)) + "\n")
            self.assertEqual(len(load(p)), 3)

    def test_tool_name_without_operation_is_a_tool(self):
        doc = {"resourceSpans": [{"scopeSpans": [{"spans": [_span("t", **{"gen_ai.tool.name": "x"})]}]}]}
        (s,) = from_otlp(doc)
        self.assertEqual(s["kind"], "tool")

    def test_child_span_keeps_its_parent(self):
        doc = {"resourceSpans": [{"scopeSpans": [{"spans": [_span("p"), _span("c", parent="p")]}]}]}
        child = from_otlp(doc)[1]
        self.assertEqual(child["parent_id"], "p")


if __name__ == "__main__":
    unittest.main()
