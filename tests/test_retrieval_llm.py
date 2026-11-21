import unittest

from pathshala.llm import parse_json
from pathshala.pipeline import format_context
from pathshala.retrieval import _is_boilerplate, _stem_en, _tsq_token, fts_or_query, fts_terms, merge_neighbor_text, rrf


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
        self.assertEqual(fts_terms("What is the difference between an acid and a base?"), ["acid", "base"])
        self.assertEqual(fts_terms("What is diffusion and how does it work in plants?"), ["diffusion", "plants"])

    def test_stem_and_tsq_token_cover_plurals_and_boilerplate(self):
        self.assertEqual(_stem_en("acids"), "acid")
        self.assertEqual(_stem_en("bases"), "base")
        self.assertEqual(_stem_en("plants"), "plant")
        self.assertEqual(_tsq_token("acids"), "acid:*")
        self.assertTrue(_is_boilerplate("Sample Questions\nMultiple Choice Questions\n1. Acid test"))
        self.assertTrue(_is_boilerplate("Stem:\na. What is diffusion?\nb. Explain osmosis."))
        self.assertFalse(_is_boilerplate("Acids turn blue litmus paper red and taste sour."))

    def test_format_context_defaults_to_six_chunks(self):
        chunks = [{"id": i, "text": f"chunk body {i}"} for i in range(1, 8)]
        ctx = format_context(chunks)
        for i in range(1, 7):
            self.assertIn(f"[{i}]", ctx)
        self.assertNotIn("[7]", ctx)

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
