import unittest

from pathshala import mastery


class TestMastery(unittest.TestCase):
    def setUp(self):
        mastery.clear_all()

    def test_ewma_updates_and_difficulty_levels(self):
        self.assertEqual(mastery.difficulty_for_mastery(0.30), "recall")
        self.assertEqual(mastery.difficulty_for_mastery(0.60), "understanding")
        self.assertEqual(mastery.difficulty_for_mastery(0.85), "application")

        s = 0.5
        for _ in range(3):
            s = mastery.update_ewma(s, False)
        self.assertLess(s, 0.20)

    def test_three_wrong_attempts_recommends_chapter_review(self):
        for _ in range(3):
            mastery.record_attempt("s1", 5, "science", "খাদ্যশৃঙ্খল", False)
        mastery.record_attempt("s1", 5, "science", "বায়ুদূষণ", True)

        snap = mastery.get_session_mastery("s1")
        self.assertEqual(snap["recommended_chapter"]["chapter"], "খাদ্যশৃঙ্খল")
        self.assertEqual(snap["recommended_chapter"]["difficulty"], "recall")
        self.assertEqual(len(snap["weak_chapters"]), 1)

        agg = mastery.get_aggregate_mastery()
        self.assertEqual(agg[0]["chapter"], "খাদ্যশৃঙ্খল")
        self.assertEqual(agg[0]["sessions"], 1)

        csv_out = mastery.weak_chapters_csv()
        self.assertIn("class_level,subject,chapter,avg_mastery,sessions,recommended_difficulty", csv_out)
        self.assertIn("খাদ্যশৃঙ্খল", csv_out)


if __name__ == "__main__":
    unittest.main()
