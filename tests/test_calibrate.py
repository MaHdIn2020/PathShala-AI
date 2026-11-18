import unittest

from scripts.calibrate_min_score import pick_threshold, sweep_thresholds


class CalibrateMinScoreTest(unittest.TestCase):
    def test_sweep_and_pick_threshold(self):
        in_scores = [0.42, 0.46, 0.55, 0.61, 0.70, 0.72, 0.75, 0.78, 0.80, 0.85]
        off_scores = [0.15, 0.22, 0.28, 0.31, 0.36, 0.39, 0.41, 0.43, 0.44, 0.48]
        rows = sweep_thresholds(in_scores, off_scores, [0.30, 0.40, 0.45, 0.50])
        self.assertEqual(rows[0]["answer_rate"], 1.0)
        self.assertEqual(rows[2]["answer_rate"], 0.9)
        self.assertEqual(rows[2]["refusal_acc"], 0.9)
        best = pick_threshold(rows, min_answer_rate=0.90)
        self.assertEqual(best["threshold"], 0.45)


if __name__ == "__main__":
    unittest.main()

