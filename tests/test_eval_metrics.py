import unittest

from eval.run_eval import keyword_recall, score_item, summarize


class TestEval(unittest.TestCase):
    def test_keyword_recall(self):
        self.assertEqual(keyword_recall("গতি ও বেগ", ["গতি", "বেগ", "ত্বরণ"]), 2 / 3)
        self.assertEqual(keyword_recall("x", []), 0.0)

    def test_answerable_correct(self):
        it = {"id": 1, "answerable": True, "keywords": ["গতি", "বেগ"], "gold_chapters": [2]}
        r = score_item(it, {"answer": "গতি ও বেগ", "citations": [{"chapter_no": 2}], "refused": False})
        self.assertTrue(r["correct"])
        self.assertTrue(r["cite_ok"])

    def test_answerable_refused_is_wrong(self):
        it = {"id": 1, "answerable": True, "keywords": ["গতি"], "gold_chapters": [2]}
        r = score_item(it, {"answer": "", "citations": [], "refused": True})
        self.assertFalse(r["correct"])
        self.assertFalse(r["cite_ok"])

    def test_unanswerable(self):
        it = {"id": 2, "answerable": False}
        self.assertTrue(score_item(it, {"refused": True})["refusal_ok"])
        self.assertFalse(score_item(it, {"refused": False})["refusal_ok"])

    def test_summary(self):
        rows = [
            {"answerable": True, "correct": True, "cite_ok": True},
            {"answerable": True, "correct": False, "cite_ok": False},
            {"answerable": False, "refusal_ok": True},
        ]
        s = summarize(rows, [100, 200, 300], [0.0, 0.002, 0.001])
        self.assertEqual(s["answer_accuracy"], 0.5)
        self.assertEqual(s["refusal_accuracy"], 1.0)
        self.assertEqual(s["p95_latency_ms"], 200)


if __name__ == "__main__":
    unittest.main()
