import unittest

from pathshala.llm import parse_json
from pathshala.retrieval import fts_or_query, fts_terms, merge_neighbor_text, rrf


class TestRRF(unittest.TestCase):
    def test_overlap_wins(self):
        out = rrf([[1, 2, 3], [3, 2, 9]])
        self.assertIn(out[0][0], (2, 3))
        self.assertEqual({i for i, _ in out}, {1, 2, 3, 9})

    def test_top(self):
        self.assertEqual(len(rrf([[1, 2, 3]], top=2)), 2)

    def test_fts_terms_strips_stopwords_and_builds_or_query(self):
        self.assertEqual(fts_terms("খাদ্যশৃঙ্খল কাকে বলে?"), ["খাদ্যশৃঙ্খল"])
        self.assertEqual(fts_or_query("How to bake a chocolate cake?"), "bake | chocolate | cake")

    def test_merge_neighbor_text_expands_only_short_fragments(self):
        short_c = {"id": 1, "text": "Chapter 3"}
        nbr = {"text": "Diffusion is the movement of molecules."}
        merged = merge_neighbor_text(short_c, nbr, min_chars=180)
        self.assertIn("Chapter 3", merged["text"])
        self.assertIn("Diffusion", merged["text"])
        long_c = {"id": 2, "text": "A" * 200}
        self.assertEqual(merge_neighbor_text(long_c, nbr, min_chars=180)["text"], long_c["text"])


class TestParseJson(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_json('{"a": 1}'), {"a": 1})

    def test_fenced(self):
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_noise(self):
        self.assertEqual(parse_json('here: {"a": 2} done'), {"a": 2})

    def test_garbage(self):
        self.assertEqual(parse_json("nope"), {})


if __name__ == "__main__":
    unittest.main()
