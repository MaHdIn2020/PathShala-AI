import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from pathshala.api import app
from pathshala.db import format_teacher_summary

client = TestClient(app)


class TeacherSummaryTest(unittest.TestCase):
    def test_format_teacher_summary_empty(self):
        out = format_teacher_summary(None, [], [])
        self.assertEqual(out["total_queries"], 0)
        self.assertEqual(out["refusal_rate"], 0.0)
        self.assertEqual(out["helpful_rate"], 0.0)
        self.assertFalse(out["has_seed_data"])
        self.assertEqual(out["chapters"], [])
        self.assertEqual(out["top_questions"], [])

    def test_format_teacher_summary_rates_and_chapters(self):
        totals = {
            "total_queries": 100,
            "seed_queries": 90,
            "real_queries": 10,
            "refused_queries": 25,
            "feedback_count": 40,
            "helpful_count": 30,
        }
        chapters = [
            {
                "class_level": 5,
                "subject": "math",
                "topic": "ভগ্নাংশ",
                "n": 20,
                "refused": 5,
                "seed_n": 18,
                "real_n": 2,
                "feedback_count": 10,
                "helpful_count": 8,
            }
        ]
        top_q = [{"question": "ভগ্নাংশ কী?", "class_level": 5, "subject": "math", "topic": "ভগ্নাংশ", "n": 7, "refused": 1, "seed_n": 7}]
        out = format_teacher_summary(totals, chapters, top_q)
        self.assertTrue(out["has_seed_data"])
        self.assertEqual(out["refusal_rate"], 0.25)
        self.assertEqual(out["helpful_rate"], 0.75)
        self.assertEqual(out["chapters"][0]["refusal_rate"], 0.25)
        self.assertEqual(out["chapters"][0]["helpful_rate"], 0.8)
        self.assertEqual(out["top_questions"][0]["n"], 7)

    @patch("pathshala.db.teacher_summary")
    def test_endpoint_returns_summary(self, mock_summary):
        mock_summary.return_value = format_teacher_summary(
            {"total_queries": 5, "seed_queries": 5, "real_queries": 0, "refused_queries": 1, "feedback_count": 2, "helpful_count": 2},
            [],
            [],
        )
        res = client.get("/teacher/summary?limit=25")
        self.assertEqual(res.status_code, 200)
        mock_summary.assert_called_once_with(25)
        self.assertEqual(res.json()["total_queries"], 5)
        self.assertTrue(res.json()["has_seed_data"])


if __name__ == "__main__":
    unittest.main()

