import json
import os
import tempfile
import unittest
from pathlib import Path

from ingest.mendeley import load_dir, normalize_record
from pathshala import pipeline
from pathshala.config import get_config
from pathshala.retrieval import lexical_sim


def _cfg(**kw):
    os.environ.update({"VERIFY": "0", "REWRITE": "0", "CACHE": "0"})
    os.environ.update({k: str(v) for k, v in kw.items()})
    return get_config()


class CurriculumIsolationTest(unittest.TestCase):
    def setUp(self):
        pipeline._CACHE.clear()

    def test_bangla_and_english_versions_coexist_with_distinct_refs_and_pages(self):
        with tempfile.TemporaryDirectory() as d:
            bn_dir = Path(d) / "mendeley" / "classEight" / "processed_chapters_science"
            bn_dir.mkdir(parents=True)
            (bn_dir / "class8_Science_ch3.jsonl").write_text(
                json.dumps(
                    {
                        "class": 8,
                        "subject": "Science",
                        "chapter_no": 3,
                        "chapter_title": "ব্যাপন ও অভিস্রবণ",
                        "chunk_id": "8-Science-3-1",
                        "text": "ব্যাপন একটি ভৌত প্রক্রিয়া।",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (Path(d) / "mendeley" / "classEight" / "chapters_config_science.json").write_text(
                json.dumps([{"chapter_no": 3, "chapter_title": "ব্যাপন ও অভিস্রবণ", "start_page": 25, "end_page": 35}]),
                encoding="utf-8",
            )

            en_dir = Path(d) / "NCTB-SchoolText-English" / "classEight" / "processed_chapters_science"
            en_dir.mkdir(parents=True)
            (en_dir / "class8_Science_ch3.jsonl").write_text(
                json.dumps(
                    {
                        "class": 8,
                        "subject": "Science",
                        "lang": "en",
                        "chapter_no": 3,
                        "chapter_title": "Diffusion, Osmosis and Transpiration",
                        "chunk_id": "8-Science-3-1",
                        "text": "Diffusion is the movement of molecules from higher concentration to lower concentration.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (Path(d) / "NCTB-SchoolText-English" / "classEight" / "chapters_config_science.json").write_text(
                json.dumps([{"chapter_no": 3, "chapter_title": "Diffusion, Osmosis and Transpiration", "start_page": 30, "end_page": 39}]),
                encoding="utf-8",
            )

            bn_recs = load_dir(Path(d) / "mendeley")
            en_recs = load_dir(Path(d) / "NCTB-SchoolText-English")
            self.assertEqual(bn_recs[0]["textbook_medium"], "bangla_version")
            self.assertEqual(en_recs[0]["textbook_medium"], "english_version")
            self.assertNotEqual(bn_recs[0]["chunk_ref"], en_recs[0]["chunk_ref"])
            self.assertEqual(en_recs[0]["chunk_ref"], "en-8-Science-3-1")
            self.assertEqual((bn_recs[0]["page_start"], bn_recs[0]["page_end"]), (25, 35))
            self.assertEqual((en_recs[0]["page_start"], en_recs[0]["page_end"]), (30, 39))

    def test_ambiguous_medium_not_guessed(self):
        rec = normalize_record({"class": 8, "subject": "Science", "chapter_no": 1, "chunk_id": "8-Science-1-1", "text": "Cells are building blocks."})
        self.assertEqual(rec["textbook_medium"], "unknown")

    def test_english_version_never_cites_bangla_version_chunks(self):
        mixed_chunks = [
            {
                "id": 101,
                "chunk_ref": "8-Science-3-1",
                "text": "ব্যাপন প্রক্রিয়া।",
                "chapter_no": 3,
                "chapter": "ব্যাপন",
                "class_level": 8,
                "subject": "science",
                "curriculum_id": "nctb",
                "textbook_medium": "bangla_version",
                "page_start": 25,
                "page_end": 35,
                "book": "NCTB শ্রেণি 8 · science",
                "sim": 0.91,
            },
            {
                "id": 202,
                "chunk_ref": "en-8-Science-3-1",
                "text": "Diffusion is movement of molecules from higher to lower concentration.",
                "chapter_no": 3,
                "chapter": "Diffusion, Osmosis and Transpiration",
                "class_level": 8,
                "subject": "science",
                "curriculum_id": "nctb",
                "textbook_medium": "english_version",
                "page_start": 30,
                "page_end": 39,
                "book": "NCTB Class 8 · science (English Version)",
                "sim": 0.85,
            },
        ]
        # Model wrongly cites Bangla chunk 101 while answering an English Version query -> must strip 101
        cites = pipeline.clean_citations([{"chunk_id": 101}, {"chunk_id": 202}], mixed_chunks, expected_medium="english_version")
        self.assertEqual(len(cites), 1)
        self.assertEqual(cites[0]["chunk_id"], 202)
        self.assertEqual(cites[0]["textbook_medium"], "english_version")
        self.assertEqual((cites[0]["page_start"], cites[0]["page_end"]), (30, 39))

    def test_unavailable_curriculum_returns_honest_refusal(self):
        r = pipeline.answer(
            "What is water?",
            1,
            "science",
            curriculum_id="nctb",
            textbook_medium="english_version",
            answer_language="bn",
            cfg=_cfg(),
            availability_fn=lambda cls, subj, med, curr: False,
            retrieve_fn=lambda *a, **k: [{"id": 1}],
            llm_fn=lambda *a, **k: ({}, {"cost": 0.0}),
        )
        self.assertTrue(r["refused"])
        self.assertEqual(r["reason"], "unavailable_curriculum")
        self.assertEqual(r["citations"], [])

    def test_cross_language_rewrite_and_answer_language_separation(self):
        seen = {"rewrite_sys": None, "tutor_sys": None, "retrieve_med": None}

        def fake_retrieve(q, cls, subj, cfg, curriculum_id="nctb", textbook_medium="bangla_version"):
            seen["retrieve_med"] = textbook_medium
            return [
                {
                    "id": 202,
                    "chunk_ref": "en-8-Science-3-1",
                    "text": "Diffusion is movement of molecules from higher to lower concentration.",
                    "chapter_no": 3,
                    "chapter": "Diffusion, Osmosis and Transpiration",
                    "class_level": 8,
                    "subject": "science",
                    "curriculum_id": curriculum_id,
                    "textbook_medium": textbook_medium,
                    "page_start": 30,
                    "page_end": 39,
                    "book": "NCTB Class 8 · science (English Version)",
                    "sim": 0.88,
                }
            ]

        def fake_llm(system, user, model, max_tokens=1500):
            if "search query" in system.lower():
                seen["rewrite_sys"] = system
                return {"query": "diffusion molecules higher lower concentration"}, {"cost": 0.0001}
            seen["tutor_sys"] = system
            return {
                "answer": "ব্যাপন (Diffusion) হলো বেশি ঘনত্বের স্থান থেকে কম ঘনত্বের স্থানে অণুর চলাচল।",
                "steps": ["অণুসমূহ বেশি ঘনত্ব থেকে কম ঘনত্বে ছড়িয়ে পড়ে।"],
                "citations": [{"chunk_id": 202}],
                "confidence": 0.92,
            }, {"cost": 0.0005}

        r = pipeline.answer(
            "ব্যাপন কাকে বলে?",
            8,
            "science",
            curriculum_id="nctb",
            textbook_medium="english_version",
            answer_language="bn",
            cfg=_cfg(REWRITE=1, VERIFY=0),
            retrieve_fn=fake_retrieve,
            llm_fn=fake_llm,
            availability_fn=lambda *a: True,
        )
        self.assertFalse(r["refused"])
        self.assertEqual(seen["retrieve_med"], "english_version")
        self.assertIn("English", seen["rewrite_sys"])
        self.assertIn("NCTB English Version", seen["tutor_sys"])
        self.assertIn("Bangla", seen["tutor_sys"])
        self.assertEqual(r["citations"][0]["page_start"], 30)
        self.assertEqual(r["citations"][0]["page_end"], 39)

    def test_lexical_sim_blocks_incidental_single_hit_on_long_off_syllabus_query(self):
        self.assertLess(lexical_sim(["bake", "chocolate", "cake"], "She ate a slice of cake at the party."), 0.45)
        self.assertGreaterEqual(lexical_sim(["diffusion", "osmosis", "plants"], "Diffusion and osmosis occur in plants."), 0.70)


if __name__ == "__main__":
    unittest.main()
