import contextlib
import io
import pathlib
import tempfile
import unittest

from agent_tracer.__main__ import main
from agent_tracer.core import load
from agent_tracer.dashboard import render

EX = pathlib.Path(__file__).resolve().parent.parent / "examples"


class DashboardTests(unittest.TestCase):
    def test_totals_timeline_models_and_errors(self):
        page = render(load(str(EX / "trace.jsonl")), "run")
        for text in ("Traces", "20,410", "$0.3458", "claude-opus", "fetch_page", "read timed out", "1 error"):
            self.assertIn(text, page)
        self.assertNotIn("<script", page)

    def test_hostile_values_are_escaped(self):
        spans = [
            {
                "trace_id": "<t>",
                "span_id": "a",
                "parent_id": None,
                "name": "<img src=x onerror=alert(1)>",
                "kind": "tool",
                "start": 1.0,
                "end": 2.0,
                "duration_ms": 1000,
                "attrs": {"model": "<b>m</b>"},
                "status": "error",
                "error": "<script>x</script>",
            }
        ]
        page = render(spans, "<title>")
        self.assertNotIn("<img src=x", page)
        self.assertNotIn("<script>x", page)
        self.assertIn("&lt;img src=x", page)

    def test_cli_writes_the_file_for_both_input_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            for src in ("trace.jsonl", "otlp-trace.json"):
                out = pathlib.Path(tmp) / f"{src}.html"
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    self.assertEqual(main(["dashboard", str(EX / src), str(out)]), 0)
                self.assertTrue(out.read_text(encoding="utf-8").startswith("<!doctype html>"))


if __name__ == "__main__":
    unittest.main()
