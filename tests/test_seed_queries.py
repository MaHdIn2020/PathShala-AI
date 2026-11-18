import unittest

from scripts.seed_queries import build_seed_rows


class SeedQueriesTest(unittest.TestCase):
    def test_count_and_fields(self):
        rows = build_seed_rows(300)
        self.assertEqual(len(rows), 300)
        for r in rows:
            self.assertEqual(r["session_id"], "seed")
            self.assertIn(r["class_level"], range(1, 6))
            self.assertTrue(r["question"].strip())
            self.assertTrue(r["topic"].strip())

    def test_refused_mix_and_repeats(self):
        rows = build_seed_rows(300)
        refused = [r for r in rows if r["refused"]]
        answered = [r for r in rows if not r["refused"]]
        self.assertGreater(len(refused), 0)
        self.assertGreater(len(answered), 0)
        self.assertLess(len({r["question"] for r in rows}), len(rows))


if __name__ == "__main__":
    unittest.main()

