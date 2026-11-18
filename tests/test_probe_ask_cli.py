import unittest

from scripts.ask import DEFAULT_QUESTIONS as ASK_QUESTIONS
from scripts.ask import format_ask_result
from scripts.probe import DEFAULT_QUESTIONS as PROBE_QUESTIONS
from scripts.probe import format_probe_results


class ProbeAskCliTest(unittest.TestCase):
    def test_default_question_sets_have_ten_primary_items(self):
        self.assertEqual(len(PROBE_QUESTIONS), 10)
        self.assertEqual(len(ASK_QUESTIONS), 10)
        self.assertTrue(all(cls in range(1, 6) for _, cls, _ in PROBE_QUESTIONS))
        self.assertTrue(all(cls in range(1, 6) for _, cls, _, _ in ASK_QUESTIONS))

    def test_format_probe_results_truncates_snippet_and_shows_metadata(self):
        long_text = "ক" * 120
        out = format_probe_results(
            "প্রশ্ন",
            5,
            "bangla",
            [{"id": 1, "chunk_ref": "5-Bangla-1-1", "sim": 0.8123, "chapter_no": 1, "chapter": "পাঠ", "text": long_text}],
        )
        self.assertIn("5-Bangla-1-1", out)
        self.assertIn("0.812", out)
        self.assertIn("ch=1:পাঠ", out)
        self.assertIn("ক" * 80, out)
        self.assertNotIn("ক" * 81, out)
        self.assertIn("(no results)", format_probe_results("প্রশ্ন", 5, None, []))

    def test_format_ask_result_handles_answered_and_refused(self):
        answered = format_ask_result(
            "প্রশ্ন",
            5,
            {
                "refused": False,
                "reason": None,
                "top_score": 0.85,
                "latency_ms": 420,
                "cost_usd": 0.00012,
                "answer": "সঠিক উত্তর",
                "citations": [{"class_level": 5, "subject": "bangla", "chapter_no": 1, "chapter": "পাঠ", "chunk_ref": "5-Bangla-1-1"}],
            },
        )
        self.assertIn("refused=False", answered)
        self.assertIn("5-Bangla-1-1", answered)

        refused = format_ask_result("অজানা", 5, {"refused": True, "reason": "low_retrieval", "answer": "খুঁজে পাইনি", "citations": []})
        self.assertIn("refused=True reason=low_retrieval", refused)


if __name__ == "__main__":
    unittest.main()

