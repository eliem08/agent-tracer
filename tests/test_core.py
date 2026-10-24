import os
import tempfile
import unittest

from agent_tracer import Tracer, build_tree, load, stats


class Tests(unittest.TestCase):
    def test_nesting_cost_and_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.jsonl")
            tr = Tracer(path)

            @tr.trace(kind="tool")
            def boom():
                raise RuntimeError("404")

            with tr.span("agent", kind="agent"):
                with tr.span("plan", kind="llm", model="claude-sonnet-x", input_tokens=1_000_000, output_tokens=0):
                    pass
                try:
                    boom()
                except RuntimeError:
                    pass
            spans = load(path)
            self.assertEqual(len(spans), 3)
            root = [s for s in spans if s["parent_id"] is None]
            self.assertEqual(len(root), 1)
            self.assertEqual({s["trace_id"] for s in spans}, {root[0]["trace_id"]})
            plan = next(s for s in spans if s["name"] == "plan")
            self.assertAlmostEqual(plan["attrs"]["cost_usd"], 3.0)
            st = stats(spans)
            self.assertEqual(st["errors"], 1)
            self.assertIn("RuntimeError", next(s for s in spans if s["name"] == "boom")["error"])
            tree = build_tree(spans)
            (roots,) = tree.values()
            self.assertEqual([c["name"] for c in roots[0]["children"]], ["plan", "boom"])

    def test_separate_traces(self):
        tr = Tracer()
        with tr.span("a"):
            pass
        with tr.span("b"):
            pass
        self.assertEqual(len({s["trace_id"] for s in tr.spans}), 2)


if __name__ == "__main__":
    unittest.main()
