import unittest
from types import SimpleNamespace

from pathshala.practice import practice

CHUNKS = [
    {"id": 1, "chunk_ref": "5-Math-1-1", "text": "গুণ", "sim": 0.8},
    {"id": 2, "chunk_ref": "5-Math-1-2", "text": "ভাগ", "sim": 0.7},
]
CFG = SimpleNamespace(max_question_chars=600, min_score=0.35, llm_model="m", max_context_chars=6000)


def retrieve(*a, **k):
    return CHUNKS


def llm_with(items):
    return lambda system, user, model, mt: ({"questions": items}, {"cost": 0.001})


def item(cid, q="প্রশ্ন?"):
    return {"q": q, "a": "উত্তর", "chunk_id": cid, "level": "recall"}


class PracticeTest(unittest.TestCase):
    def test_returns_three_grounded_questions(self):
        r = practice("গুণ", 5, cfg=CFG, retrieve_fn=retrieve, llm_fn=llm_with([item(1), item(2), item(1)]))
        self.assertFalse(r["refused"])
        self.assertEqual(len(r["questions"]), 3)
        self.assertTrue(all(q["chunk_id"] in (1, 2) for q in r["questions"]))
        self.assertEqual(r["questions"][1]["chunk_ref"], "5-Math-1-2")

    def test_drops_invented_chunk_ids_and_refuses_if_short(self):
        r = practice("গুণ", 5, cfg=CFG, retrieve_fn=retrieve, llm_fn=llm_with([item(1), item(2), item(99)]))
        self.assertTrue(r["refused"])
        self.assertEqual(r["reason"], "not_enough_grounded_questions")

    def test_low_retrieval_refuses(self):
        low = lambda *a, **k: [{**CHUNKS[0], "sim": 0.01}]  # noqa: E731
        r = practice("রান্না", 5, cfg=CFG, retrieve_fn=low, llm_fn=llm_with([]))
        self.assertTrue(r["refused"])
        self.assertEqual(r["reason"], "low_retrieval")

    def test_empty_topic(self):
        self.assertEqual(practice("  ", 5, cfg=CFG)["reason"], "empty_topic")


if __name__ == "__main__":
    unittest.main()
