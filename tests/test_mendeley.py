import json
import tempfile
import unittest
from pathlib import Path

from ingest.mendeley import load_dir, normalize_record, to_int


class TestNorm(unittest.TestCase):
    def test_to_int(self):
        self.assertEqual(to_int("Class 3"), 3)
        self.assertEqual(to_int("৩"), 3)
        self.assertEqual(to_int(4), 4)
        self.assertIsNone(to_int("x"))

    def test_documented_schema(self):
        r = normalize_record({"class": 3, "subject": "Math", "chapter_no": 2, "chapter_title": "যোগ", "chunk_id": "3-Math-2-1", "text": " হ্যালো "})
        self.assertEqual((r["class_level"], r["subject"], r["chapter_no"], r["chunk_ref"], r["text"]), (3, "math", 2, "3-Math-2-1", "হ্যালো"))

    def test_aliases(self):
        r = normalize_record({"grade": "Class 5", "subject": "Bangla Literature", "chapter_number": "১২", "chapter_name": "ক", "id": "x", "content": "টেক্সট"})
        self.assertEqual((r["class_level"], r["subject"], r["chapter_no"]), (5, "bangla_literature", 12))

    def test_unusable(self):
        self.assertIsNone(normalize_record({"class": 3, "subject": "m", "text": "  "}))
        self.assertIsNone(normalize_record({"subject": "m", "text": "x"}))


class TestLoad(unittest.TestCase):
    def test_jsonl_json_and_nested(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "a.jsonl").write_text(
                "\n".join(json.dumps(x, ensure_ascii=False) for x in [
                    {"class": 3, "subject": "math", "chapter_no": 1, "chapter_title": "সংখ্যা", "chunk_id": "3-math-1-1", "text": "এক"},
                    {"class": 3, "subject": "math", "chapter_no": 1, "chapter_title": "সংখ্যা", "chunk_id": "3-math-1-1", "text": "dup"},
                ]) + "\n\nnot json\n",
                encoding="utf-8",
            )
            (d / "b.json").write_text(json.dumps([{"class": 4, "subject": "english", "chapter_no": 2, "chapter_title": "Hello", "text": "Hi there"}]), encoding="utf-8")
            (d / "c.json").write_text(
                json.dumps({"class": 5, "subject": "science", "chapters": [{"chapter_no": 3, "chapter_title": "পানি", "chunks": [{"text": "পানি তরল"}, {"text": "বরফ কঠিন"}]}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            recs = load_dir(d)
            refs = sorted(r["chunk_ref"] for r in recs)
            self.assertEqual(refs, ["3-math-1-1", "4-english-2-1", "5-science-3-1", "5-science-3-2"])
            sci = [r for r in recs if r["subject"] == "science"]
            self.assertEqual({r["chapter_no"] for r in sci}, {3})
            self.assertEqual(sci[0]["chapter"], "পানি")


if __name__ == "__main__":
    unittest.main()
