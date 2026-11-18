import json
import tempfile
import unittest
from pathlib import Path

from ingest.mendeley import load_dir, normalize_record

REAL = {"class": 5, "subject": "Math", "chapter_no": 1, "chapter_title": "গুণ ও ভাগ", "chunk_id": "5-Math-1-1", "text": "এখানে, গুণ্য ৪৬১৪"}


class RealShapeTest(unittest.TestCase):
    def test_real_record(self):
        r = normalize_record(REAL)
        self.assertEqual((r["class_level"], r["subject"], r["chapter_no"], r["chunk_ref"]), (5, "math", 1, "5-Math-1-1"))
        self.assertEqual(r["chapter"], "গুণ ও ভাগ")

    def test_combined_ssc_class_maps_to_first_number(self):
        r = normalize_record({**REAL, "class": "9-10", "chunk_id": "9-10-Physics-1-1"})
        self.assertEqual(r["class_level"], 9)

    def test_load_dir_reads_chapter_jsonl_and_skips_config_json(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "classFive" / "processed_chapters_math"
            sub.mkdir(parents=True)
            (sub / "class5_Math_ch1.jsonl").write_text(json.dumps(REAL, ensure_ascii=False) + "\n", encoding="utf-8")
            cfg = [{"chapter_no": 1, "chapter_title": "গুণ ও ভাগ", "start_page": 6, "end_page": 19}]
            (Path(d) / "classFive" / "chapters_config_math.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
            recs = load_dir(d)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["chunk_ref"], "5-Math-1-1")


if __name__ == "__main__":
    unittest.main()
