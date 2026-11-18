import unittest
from unittest.mock import patch

from mcp_server import server


class McpServerTest(unittest.TestCase):
    @patch("mcp_server.server.retrieval.search")
    def test_search_textbook_clamps_k_and_filters_fields(self, mock_search):
        mock_search.return_value = [
            {
                "id": 1,
                "chunk_ref": "5-Bangla-1-1",
                "book": "NCTB শ্রেণি 5 · bangla",
                "book_id": 1,
                "class_level": 5,
                "subject": "bangla",
                "chapter_no": 1,
                "chapter": "বৈচিত্র্যময় বাংলাদেশ",
                "text": "পাঠ ১",
                "contextual_text": "extra hidden context",
                "sim": 0.91,
            }
        ]
        res = server.search_textbook("বাংলাদেশ", 5, subject="bangla", k=50)
        mock_search.assert_called_once_with("বাংলাদেশ", 5, "bangla", k=10)
        self.assertEqual(len(res), 1)
        self.assertNotIn("contextual_text", res[0])
        self.assertEqual(res[0]["chunk_ref"], "5-Bangla-1-1")

        server.search_textbook("বাংলাদেশ", 5, k=0)
        mock_search.assert_called_with("বাংলাদেশ", 5, None, k=1)

    @patch("mcp_server.server.db.get_chapter")
    @patch("mcp_server.server.db.list_chapters")
    def test_get_chapter_and_list_chapters(self, mock_list, mock_get):
        mock_list.return_value = [{"chapter_no": 1, "chapter": "বৈচিত্র্যময় বাংলাদেশ", "chunks": 10}]
        mock_get.return_value = [{"id": 1, "chunk_ref": "5-Bangla-1-1", "text": "পাঠ ১", "chapter_no": 1, "chapter": "বৈচিত্র্যময় বাংলাদেশ"}]
        self.assertEqual(server.list_chapters(1), mock_list.return_value)
        self.assertEqual(server.get_chapter(1, 1), mock_get.return_value)
        mock_list.assert_called_once_with(1)
        mock_get.assert_called_once_with(1, 1)

    @patch("mcp_server.server.db.get_chunk")
    def test_explain_citation_found_and_missing(self, mock_get_chunk):
        mock_get_chunk.return_value = {"id": 1, "chunk_ref": "5-Bangla-1-1", "text": "পাঠ ১"}
        self.assertEqual(server.explain_citation(1)["chunk_ref"], "5-Bangla-1-1")

        mock_get_chunk.return_value = None
        self.assertEqual(server.explain_citation(999), {"error": "not found"})


if __name__ == "__main__":
    unittest.main()
