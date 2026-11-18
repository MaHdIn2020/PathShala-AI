import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from pathshala.api import app

client = TestClient(app)


class ApiImageTest(unittest.TestCase):
    def test_image_oversize_rejected(self):
        huge_base64 = "A" * 3_000_000
        res = client.post("/ask-image", json={"image_base64": huge_base64, "class_level": 5})
        self.assertEqual(res.status_code, 413)

    @patch("pathshala.llm.chat_image_json")
    @patch("pathshala.pipeline.answer")
    @patch("pathshala.db.log_query")
    def test_image_transcription_and_pipeline(self, mock_log, mock_answer, mock_ocr):
        mock_ocr.return_value = ({"question": "বাংলাদেশের রাজধানীর নাম কি?"}, {"cost": 0.0002})
        mock_answer.return_value = {
            "answer": "ঢাকা",
            "steps": [],
            "citations": [],
            "confidence": 0.95,
            "refused": False,
            "reason": None,
            "top_score": 0.8,
            "topic": "বাংলাদেশ",
            "latency_ms": 150,
            "cost_usd": 0.0005,
            "cached": False,
        }
        mock_log.return_value = 123

        res = client.post(
            "/ask-image",
            json={
                "image_base64": "dGVzdA==",
                "mime_type": "image/jpeg",
                "class_level": 5,
                "subject": "বাংলা",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["answer"], "ঢাকা")
        self.assertEqual(data["transcribed_question"], "বাংলাদেশের রাজধানীর নাম কি?")
        self.assertEqual(data["query_id"], 123)


if __name__ == "__main__":
    unittest.main()
