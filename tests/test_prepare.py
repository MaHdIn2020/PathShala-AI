import unittest

from ingest.prepare import prepare


def rec(ref, text, cls=1):
    return {"class_level": cls, "subject": "math", "chapter_no": 1, "chapter": "c", "chunk_ref": ref, "text": text}


class PrepareTest(unittest.TestCase):
    def test_drops_empty_and_duplicate_refs(self):
        out, st = prepare([rec("1-a", "  "), rec("1-b", "ok"), rec("1-b", "again")])
        self.assertEqual([r["chunk_ref"] for r in out], ["1-b"])
        self.assertEqual((st["dropped_empty"], st["dropped_duplicate_ref"]), (1, 1))

    def test_splits_oversize_with_suffix_and_cap(self):
        text = " ".join(["বাক্য আছে।"] * 400)
        out, st = prepare([rec("1-x", text)], max_chars=500)
        self.assertGreater(len(out), 1)
        self.assertTrue(all(len(r["text"]) <= 500 for r in out))
        self.assertEqual([r["chunk_ref"] for r in out[:2]], ["1-x-a", "1-x-b"])
        self.assertEqual(st["split_chunks"], 1)

    def test_class_filter(self):
        out, st = prepare([rec("1-a", "x", 5), rec("6-a", "y", 6)], max_class=5)
        self.assertEqual(len(out), 1)
        self.assertEqual(st["skipped_class"], 1)
        out, _ = prepare([rec("6-a", "y", 6)], max_class=0)
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
