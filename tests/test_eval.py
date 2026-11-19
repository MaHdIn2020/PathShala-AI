import unittest

from eval.error_analysis import classify_failure
from eval.run_eval import judge_prompt, parse_judge_verdict, score_item, summarize


class TestEval(unittest.TestCase):
    def test_classify_failure(self):
        self.assertEqual(classify_failure({"refused": True, "cite_ok": False}), "retrieval_miss")
        self.assertEqual(classify_failure({"refused": False, "cite_ok": True}), "metric_artifact")
        self.assertEqual(classify_failure({"refused": False, "cite_ok": False}), "generation_error")

    def test_judge_helpers_and_summarize(self):
        prompt = judge_prompt("খাদ্যশৃঙ্খল কী?", "উদ্ভিদ থেকে প্রাণী", ["উদ্ভিদ", "প্রাণী"])
        self.assertIn("খাদ্যশৃঙ্খল কী?", prompt)
        self.assertTrue(parse_judge_verdict({"verdict": "PASS"}))
        self.assertFalse(parse_judge_verdict({"verdict": "FAIL"}))

        item = {"id": "1", "answerable": True, "keywords": ["খাদ্যশৃঙ্খল"], "gold_chapters": [1]}
        resp = {"refused": False, "answer": "ভিন্ন শব্দে উত্তর", "citations": [{"chapter_no": 1}]}
        row = score_item(item, resp, judge_fn=lambda it, r: True)
        self.assertFalse(row["correct"])
        self.assertTrue(row["judge_ok"])
        summary = summarize([row], [100], [0.001])
        self.assertEqual(summary["llm_judge_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
