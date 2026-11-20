import unittest

from pathshala.math_tool import safe_eval_expr
from pathshala.pipeline import is_distress_query, subject_min_score
from pathshala.text import normalize_for_retrieval, normalize_query


class TestMathAndNorm(unittest.TestCase):
    def test_normalize_query_digits_and_subject_hint(self):
        q, hint = normalize_query("শ্রেণি ৫ বিজ্ঞান অধ্যায় ৩?")
        self.assertEqual(q, "শ্রেণি 5 বিজ্ঞান অধ্যায় 3")
        self.assertEqual(hint, "science")

    def test_safe_eval_expr_bangla_and_safety(self):
        self.assertEqual(safe_eval_expr("১২ + ৮ × ২"), 28)
        self.assertEqual(safe_eval_expr("(100 - 25) / 5"), 15)
        self.assertIsNone(safe_eval_expr("10 / 0"))
        self.assertIsNone(safe_eval_expr("__import__('os').system('ls')"))

    def test_subject_min_score_and_banglish_distress(self):
        self.assertEqual(subject_min_score("math", 0.45), 0.42)
        self.assertEqual(subject_min_score(None, 0.45), 0.45)
        self.assertTrue(is_distress_query("ami more jete chai"))
        self.assertTrue(is_distress_query("ami bachte chai na"))
        self.assertTrue(is_distress_query("bachte iccha kore na"))
        self.assertTrue(is_distress_query("don't want to live"))

    def test_banglish_retrieval_normalization_preserves_and_expands(self):
        orig = "khadya shringkhol ki?"
        norm = normalize_for_retrieval(orig)
        self.assertIn("khadya shringkhol", norm)
        self.assertIn("খাদ্যশৃঙ্খল", norm)
        self.assertIn("bapon", normalize_for_retrieval("bapon ki?"))
        self.assertIn("diffusion", normalize_for_retrieval("bapon ki?"))


if __name__ == "__main__":
    unittest.main()
