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

    def test_concept_gaps_and_small_cohort_privacy_suppression(self):
        gaps = [
            {
                "curriculum_id": "nctb",
                "textbook_medium": "english_version",
                "class_level": 8,
                "subject": "science",
                "chapter": "Diffusion, Osmosis and Transpiration",
                "attempts": 12,
                "incorrect_count": 5,
                "seed_attempts": 12,
                "real_attempts": 0,
                "unique_sessions": 4,
                "avg_mastery": 0.48,
            },
            {
                "curriculum_id": "nctb",
                "textbook_medium": "bangla_version",
                "class_level": 5,
                "subject": "math",
                "chapter": "ভগ্নাংশ",
                "attempts": 2,
                "incorrect_count": 2,
                "seed_attempts": 0,
                "real_attempts": 2,
                "unique_sessions": 1,
                "avg_mastery": 0.25,
            },
        ]
        misc = [
            {
                "likely_misconception": "Likely misconception: confusing diffusion with osmosis",
                "textbook_medium": "english_version",
                "class_level": 8,
                "subject": "science",
                "chapter": "Diffusion, Osmosis and Transpiration",
                "count": 4,
                "seed_count": 4,
                "real_count": 0,
                "unique_sessions": 4,
            },
            {
                "likely_misconception": "Private single student misconception",
                "textbook_medium": "bangla_version",
                "class_level": 5,
                "subject": "math",
                "chapter": "ভগ্নাংশ",
                "count": 1,
                "seed_count": 0,
                "real_count": 1,
                "unique_sessions": 1,
            },
        ]
        out = format_teacher_summary(None, [], [], concept_gaps=gaps, misconceptions=misc, min_group_size=3)
        self.assertEqual(len(out["concept_gaps"]), 1)
        self.assertEqual(out["concept_gaps"][0]["textbook_medium"], "english_version")
        self.assertAlmostEqual(out["concept_gaps"][0]["incorrect_rate"], round(5 / 12, 4))
        self.assertTrue(out["concept_gaps"][0]["is_demo_data"])
        self.assertEqual(len(out["recurring_misconceptions"]), 1)
        self.assertEqual(out["suppressed_small_groups"], 2)


if __name__ == "__main__":
    unittest.main()

