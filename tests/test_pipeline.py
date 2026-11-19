import os
import unittest

from pathshala import pipeline
from pathshala.config import get_config
from pathshala.pipeline import (
    REFUSAL,
    SAFETY_MESSAGE,
    answer,
    clean_citations,
    format_context,
    should_rewrite,
    should_skip_verify,
)

CHUNKS = [
    {"id": 7, "chunk_ref": "3-math-2-4", "text": "গতি হলো সময়ের সাথে অবস্থানের পরিবর্তন।", "chapter_no": 2, "chapter": "যোগ", "class_level": 3, "subject": "math", "page_start": None, "page_end": None, "book": "গণিত ৩", "sim": 0.8}
]


def _cfg(**kw):
    os.environ.update({"VERIFY": "0", "REWRITE": "0", "CACHE": "0"})
    os.environ.update({k: str(v) for k, v in kw.items()})
    return get_config()


def retrieve_ok(*a, **k):
    return CHUNKS


def llm_factory(answer_obj, verdict="PASS"):
    def fn(system, user, model, max_tokens=1500):
        if "verifier" in system.lower() or "claim" in system.lower():
            return {"verdict": verdict}, {"cost": 0.0}
        return answer_obj, {"cost": 0.001}

    return fn


GOOD = {"answer": "গতি হলো অবস্থানের পরিবর্তন।", "steps": ["ধাপ ১"], "citations": [{"chunk_id": 7}], "confidence": 0.9}


class TestPipeline(unittest.TestCase):
    def setUp(self):
        pipeline._CACHE.clear()

    def test_happy_path(self):
        r = answer("গতি কী?", 9, "physics", cfg=_cfg(), retrieve_fn=retrieve_ok, llm_fn=llm_factory(GOOD))
        self.assertFalse(r["refused"])
        self.assertEqual(r["citations"][0]["chunk_id"], 7)
        self.assertEqual(r["citations"][0]["chapter_no"], 2)
        self.assertEqual(r["citations"][0]["chunk_ref"], "3-math-2-4")
        self.assertEqual(r["citations"][0]["book"], "গণিত ৩")

    def test_low_retrieval_refuses(self):
        low = lambda *a, **k: [{**CHUNKS[0], "sim": 0.01}]  # noqa: E731
        r = answer("রান্না কীভাবে করব?", 9, cfg=_cfg(), retrieve_fn=low, llm_fn=llm_factory(GOOD))
        self.assertTrue(r["refused"])
        self.assertEqual(r["answer"], REFUSAL)
        self.assertEqual(r["reason"], "low_retrieval")

    def test_empty_retrieval_refuses(self):
        r = answer("প্রশ্ন", 9, cfg=_cfg(), retrieve_fn=lambda *a, **k: [], llm_fn=llm_factory(GOOD))
        self.assertTrue(r["refused"])

    def test_invented_chunk_refuses(self):
        bad = {**GOOD, "citations": [{"chunk_id": 999}]}
        r = answer("গতি কী?", 9, cfg=_cfg(), retrieve_fn=retrieve_ok, llm_fn=llm_factory(bad))
        self.assertTrue(r["refused"])
        self.assertEqual(r["reason"], "no_valid_citation")

    def test_model_supplied_fields_are_ignored(self):
        c = clean_citations([{"chunk_id": 7, "chapter_no": 99, "book": "fake"}], CHUNKS)
        self.assertEqual((c[0]["chapter_no"], c[0]["book"]), (2, "গণিত ৩"))

    def test_duplicate_citations_deduped(self):
        self.assertEqual(len(clean_citations([{"chunk_id": 7}, {"chunk_id": "7"}], CHUNKS)), 1)

    def test_clean_citations_accepts_id_variants_only_from_retrieved_chunks(self):
        c = clean_citations([{"id": 7}, 7, "999", None], CHUNKS)
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0]["chunk_id"], 7)

    def test_verifier_fail_refuses(self):
        r = answer("গতি কী?", 9, cfg=_cfg(VERIFY=1), retrieve_fn=retrieve_ok, llm_fn=llm_factory(GOOD, verdict="FAIL"))
        self.assertTrue(r["refused"])
        self.assertEqual(r["reason"], "verifier_fail")

    def test_verifier_retry_succeeds_on_second_attempt(self):
        calls = {"ans": [], "ver": 0}

        def fn(system, user, model, max_tokens=1500):
            if "verifier" in system.lower() or "claim" in system.lower():
                calls["ver"] += 1
                return {"verdict": "FAIL" if calls["ver"] == 1 else "PASS"}, {"cost": 0.0}
            calls["ans"].append(user)
            return GOOD, {"cost": 0.001}

        r = answer("গতি কী?", 9, cfg=_cfg(VERIFY=1), retrieve_fn=retrieve_ok, llm_fn=fn)
        self.assertFalse(r["refused"])
        self.assertEqual(len(calls["ans"]), 2)
        self.assertIn("fix unsupported claims", calls["ans"][1])
        self.assertEqual(calls["ver"], 2)

    def test_verifier_retry_refuses_after_second_fail(self):
        calls = {"ans": 0, "ver": 0}

        def fn(system, user, model, max_tokens=1500):
            if "verifier" in system.lower() or "claim" in system.lower():
                calls["ver"] += 1
                return {"verdict": "FAIL"}, {"cost": 0.0}
            calls["ans"] += 1
            return GOOD, {"cost": 0.001}

        r = answer("গতি কী?", 9, cfg=_cfg(VERIFY=1), retrieve_fn=retrieve_ok, llm_fn=fn)
        self.assertTrue(r["refused"])
        self.assertEqual(r["reason"], "verifier_fail")
        self.assertEqual(calls["ans"], 2)
        self.assertEqual(calls["ver"], 2)

    def test_verifier_pass(self):
        r = answer("গতি কী?", 9, cfg=_cfg(VERIFY=1), retrieve_fn=retrieve_ok, llm_fn=llm_factory(GOOD))
        self.assertFalse(r["refused"])

    def test_model_says_not_in_book(self):
        r = answer("গতি কী?", 9, cfg=_cfg(), retrieve_fn=retrieve_ok, llm_fn=llm_factory({"answer": REFUSAL, "citations": []}))
        self.assertTrue(r["refused"])
        self.assertEqual(r["reason"], "model_refused")

    def test_cache_hit(self):
        cfg = _cfg(CACHE=1)
        answer("গতি কী?", 9, cfg=cfg, retrieve_fn=retrieve_ok, llm_fn=llm_factory(GOOD))
        calls = []

        def boom(*a, **k):
            calls.append(1)
            raise AssertionError("llm called on cache hit")

        r = answer("গতি কী?", 9, cfg=cfg, retrieve_fn=retrieve_ok, llm_fn=boom)
        self.assertTrue(r["cached"])
        self.assertEqual(calls, [])

    def test_distress_keyword_returns_safety_message(self):
        called = []

        def boom(*a, **k):
            called.append(1)
            raise AssertionError("should not call llm on distress query")

        for phrase in ("আমি মরে যেতে চাই", "I want to die / suicide"):
            r = answer(phrase, 5, cfg=_cfg(), retrieve_fn=boom, llm_fn=boom)
            self.assertTrue(r["refused"])
            self.assertEqual(r["reason"], "safety_distress")
            self.assertEqual(r["answer"], SAFETY_MESSAGE)
            self.assertEqual(called, [])

    def test_should_rewrite_skips_short_subject_scoped_query(self):
        self.assertFalse(should_rewrite("খাদ্যশৃঙ্খল কাকে বলে?", "science"))
        self.assertTrue(should_rewrite("খাদ্যশৃঙ্খল কাকে বলে?", None))
        self.assertTrue(should_rewrite("ক" * 50, "science"))

    def test_should_skip_verify_only_on_high_score_with_citations(self):
        self.assertTrue(should_skip_verify(0.90, [{"chunk_id": 7}]))
        self.assertFalse(should_skip_verify(0.80, [{"chunk_id": 7}]))
        self.assertFalse(should_skip_verify(0.95, []))

    def test_format_context_caps_chunks_and_trims_text(self):
        many = [{**CHUNKS[0], "id": i, "text": "ক" * 1200} for i in range(6)]
        ctx = format_context(many)
        self.assertIn("[3]", ctx)
        self.assertNotIn("[4]", ctx)
        self.assertLessEqual(len(ctx), 4000)


if __name__ == "__main__":
    unittest.main()
