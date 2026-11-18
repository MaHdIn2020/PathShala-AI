import tempfile
import unittest
from pathlib import Path

from PIL import Image

from eval.chart import render_chart


class EvalChartTest(unittest.TestCase):
    def test_render_chart_writes_valid_png(self):
        rag = {
            "n": 100,
            "answer_accuracy": 0.85,
            "citation_correctness": 0.90,
            "refusal_accuracy": 0.88,
            "p95_latency_ms": 1850,
            "mean_cost_usd": 0.00042,
        }
        base = {
            "n": 100,
            "answer_accuracy": 0.45,
            "citation_correctness": 0.0,
            "refusal_accuracy": 0.10,
            "p95_latency_ms": 920,
            "mean_cost_usd": 0.00021,
        }
        with tempfile.TemporaryDirectory() as d:
            out = render_chart(rag, base, Path(d) / "eval_chart.png")
            self.assertTrue(out.exists())
            raw = out.read_bytes()
            self.assertGreater(len(raw), 1000)
            self.assertTrue(raw.startswith(b"\x89PNG"))
            with Image.open(out) as im:
                self.assertEqual(im.size, (900, 520))


if __name__ == "__main__":
    unittest.main()

