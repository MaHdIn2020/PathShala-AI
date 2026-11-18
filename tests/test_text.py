import unittest

from pathshala.text import chunk_pages, normalize_bangla


class TestNormalize(unittest.TestCase):
    def test_strips_zero_width_and_spaces(self):
        self.assertEqual(normalize_bangla("আমি\u200b  ভাত\n\n\n\nখাই "), "আমি ভাত\n\nখাই")

    def test_keeps_zwnj(self):
        self.assertIn("\u200c", normalize_bangla("ক\u200cখ"))

    def test_ascii_digits(self):
        self.assertEqual(normalize_bangla("পৃষ্ঠা ১২৩", ascii_digits=True), "পৃষ্ঠা 123")


class TestChunk(unittest.TestCase):
    def test_page_range_and_no_loss(self):
        pages = [(1, "প্রথম অনুচ্ছেদ।\n\nদ্বিতীয় অনুচ্ছেদ।"), (2, "তৃতীয় অনুচ্ছেদ।")]
        ch = chunk_pages(pages, max_chars=1000)
        self.assertEqual(len(ch), 1)
        self.assertEqual((ch[0]["page_start"], ch[0]["page_end"]), (1, 2))
        for p in ("প্রথম", "দ্বিতীয়", "তৃতীয়"):
            self.assertIn(p, ch[0]["text"])

    def test_respects_max_chars(self):
        para = "বাক্য এক। " * 200
        ch = chunk_pages([(5, para)], max_chars=300)
        self.assertGreater(len(ch), 1)
        self.assertTrue(all(len(c["text"]) <= 300 * 1.25 for c in ch))
        self.assertTrue(all(c["page_start"] == 5 for c in ch))

    def test_chapter_heading_splits(self):
        pages = [(1, "অধ্যায় ১ গতি\n\nগতির সংজ্ঞা।"), (2, "অধ্যায় ২ বল\n\nবলের সংজ্ঞা।")]
        ch = chunk_pages(pages, max_chars=1000)
        self.assertEqual(len(ch), 2)
        self.assertTrue(ch[0]["chapter"].startswith("অধ্যায় ১"))
        self.assertTrue(ch[1]["chapter"].startswith("অধ্যায় ২"))

    def test_empty(self):
        self.assertEqual(chunk_pages([(1, "   ")]), [])


if __name__ == "__main__":
    unittest.main()
