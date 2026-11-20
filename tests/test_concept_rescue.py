import os
import unittest

from pathshala import concept_rescue, mastery
from pathshala.config import get_config


def _cfg():
    os.environ.update({"VERIFY": "0", "REWRITE": "0", "CACHE": "0"})
    return get_config()


EN_CHUNKS = [
    {
        "id": 301,
        "chunk_ref": "en-8-Science-3-1",
        "book": "NCTB Class 8 · science (English Version)",
        "curriculum_id": "nctb",
        "textbook_medium": "english_version",
        "class_level": 8,
        "subject": "science",
        "chapter_no": 3,
        "chapter": "Diffusion, Osmosis and Transpiration",
        "page_start": 30,
        "page_end": 39,
        "text": "Diffusion is the movement of molecules from higher concentration to lower concentration. Osmosis is the movement of water through a semi-permeable membrane.",
        "sim": 0.85,
    }
]


class ConceptRescueTest(unittest.TestCase):
    def setUp(self):
        mastery.clear_all()

    def test_diagnostic_check_grounded_and_isolated(self):
        def fake_llm(system, user, model, max_tokens=900):
            return (
                {
                    "learning_objective": "Distinguish diffusion from osmosis",
                    "question_text": "Which process involves water moving through a semi-permeable membrane?",
                    "options": [
                        {"id": "A", "text": "Osmosis"},
                        {"id": "B", "text": "Diffusion"},
                        {"id": "C", "text": "Combustion"},
                        {"id": "D", "text": "Evaporation"},
                    ],
                    "correct_option": "A",
                    "explanation": "Osmosis specifically moves water across a semi-permeable membrane.",
                    "misconception_labels": {
                        "B": "Confusing diffusion of general molecules with osmosis of water across a membrane",
                        "C": "Confusing physical transport with chemical burning",
                        "D": "Confusing membrane transport with surface vaporization",
                    },
                    "chunk_id": 301,
                },
                {"cost": 0.0002},
            )

        diag = concept_rescue.generate_diagnostic_check(
            "What is osmosis?",
            "Osmosis is movement of water across a semi-permeable membrane.",
            8,
            "science",
            curriculum_id="nctb",
            textbook_medium="english_version",
            answer_language="en",
            cfg=_cfg(),
            retrieve_fn=lambda *a, **k: EN_CHUNKS,
            llm_fn=fake_llm,
        )
        self.assertFalse(diag["refused"])
        self.assertEqual(diag["correct_option"], "A")
        self.assertEqual(diag["source"]["textbook_medium"], "english_version")
        self.assertEqual(diag["source"]["page_start"], 30)
        self.assertTrue(diag["misconception_labels"]["B"].startswith("Likely misconception:"))

    def test_wrong_answer_triggers_cautious_diagnosis_reteach_and_new_practice(self):
        diag = {
            "question_id": "cr-abc123",
            "curriculum_id": "nctb",
            "textbook_medium": "english_version",
            "class_level": 8,
            "subject": "science",
            "chapter_no": 3,
            "chapter": "Diffusion, Osmosis and Transpiration",
            "learning_objective": "Distinguish diffusion from osmosis",
            "question_text": "Which process involves water moving through a semi-permeable membrane?",
            "answer_language": "bn",
            "options": [
                {"id": "A", "text": "অভিস্রবণ (Osmosis)"},
                {"id": "B", "text": "ব্যাপন (Diffusion)"},
                {"id": "C", "text": "দহন"},
                {"id": "D", "text": "বাষ্পীভবন"},
            ],
            "correct_option": "A",
            "explanation": "অভিস্রবণে পানি অর্ধভেদ্য পর্দার ভেতর দিয়ে চলাচল করে।",
            "misconception_labels": {"B": "সম্ভাব্য ভুল ধারণা: ব্যাপন এবং অভিস্রবণের মধ্যে পর্দার ভূমিকা গুলিয়ে ফেলা।"},
            "source": {"chunk_id": 301, "chunk_ref": "en-8-Science-3-1", "textbook_medium": "english_version", "class_level": 8, "subject": "science", "chapter_no": 3, "chapter": "Diffusion, Osmosis and Transpiration", "page_start": 30, "page_end": 39},
        }

        def fake_reteach_llm(system, user, model, max_tokens=1200):
            return (
                {
                    "feedback": "ভালো চেষ্টা করেছ!",
                    "likely_misconception": "ব্যাপন ও অভিস্রবণের পার্থক্য (অর্ধভেদ্য পর্দা) গুলিয়ে ফেলা হচ্ছে।",
                    "confidence": 0.78,
                    "reteach_explanation": "সহজ কথায়: ব্যাপনে যেকোনো অণু খোলা জায়গায় ছড়ায়, কিন্তু অভিস্রবণে কেবল পানি একটি অর্ধভেদ্য পর্দা পার হয়ে যায়।",
                    "follow_up": {
                        "question_text": "পানি যদি অর্ধভেদ্য পর্দার ভেতর দিয়ে কম ঘনত্ব থেকে বেশি ঘনত্বে যায়, তাকে কী বলে?",
                        "options": [
                            {"id": "A", "text": "দহন"},
                            {"id": "B", "text": "অভিস্রবণ"},
                            {"id": "C", "text": "তাপ সঞ্চালন"},
                            {"id": "D", "text": "প্রতিফলন"},
                        ],
                        "correct_option": "B",
                        "explanation": "অর্ধভেদ্য পর্দার মধ্য দিয়ে পানির চলাচলই অভিস্রবণ।",
                        "misconception_labels": {"A": "রাসায়নিক বিক্রিয়া ও ভৌত প্রক্রিয়া গুলিয়ে ফেলা"},
                    },
                    "chunk_id": 301,
                },
                {"cost": 0.0003},
            )

        res = concept_rescue.submit_diagnostic_answer(
            "sess-1",
            diag,
            "B",
            event_key="evt-1",
            answer_language="bn",
            cfg=_cfg(),
            retrieve_fn=lambda *a, **k: EN_CHUNKS,
            llm_fn=fake_reteach_llm,
        )
        self.assertFalse(res["is_correct"])
        self.assertIn("সম্ভাব্য ভুল ধারণা:", res["likely_misconception"])
        self.assertIn("অর্ধভেদ্য পর্দা", res["reteach_explanation"])
        self.assertIsNotNone(res["follow_up_question"])
        self.assertNotEqual(res["follow_up_question"]["question_text"], diag["question_text"])
        self.assertEqual(res["source"]["textbook_medium"], "english_version")
        self.assertEqual(res["attempt"]["attempts"], 1)
        self.assertLess(res["attempt"]["mastery"], 0.5)

        # Duplicate submission with same event_key must not double-count
        dup = concept_rescue.submit_diagnostic_answer(
            "sess-1",
            diag,
            "B",
            event_key="evt-1",
            answer_language="bn",
            cfg=_cfg(),
            retrieve_fn=lambda *a, **k: EN_CHUNKS,
            llm_fn=fake_reteach_llm,
        )
        self.assertTrue(dup["attempt"]["duplicate"])
        self.assertEqual(dup["attempt"]["attempts"], 1)

        # Answering the follow-up correctly improves mastery
        res2 = concept_rescue.submit_diagnostic_answer(
            "sess-1",
            res["follow_up_question"],
            "B",
            event_key="evt-2",
            answer_language="bn",
            cfg=_cfg(),
        )
        self.assertTrue(res2["is_correct"])
        self.assertEqual(res2["attempt"]["attempts"], 2)
        self.assertGreater(res2["attempt"]["mastery"], res["attempt"]["mastery"])

    def test_malformed_model_output_returns_safe_fallback(self):
        diag = concept_rescue.generate_diagnostic_check(
            "What is osmosis?",
            "Water movement",
            8,
            "science",
            curriculum_id="nctb",
            textbook_medium="english_version",
            answer_language="en",
            cfg=_cfg(),
            retrieve_fn=lambda *a, **k: EN_CHUNKS,
            llm_fn=lambda *a, **k: ({"bad": "json"}, {"cost": 0.0}),
        )
        self.assertTrue(diag["refused"])
        self.assertEqual(diag["reason"], "ungrounded_diagnostic")

    def test_wrong_answer_provider_failure_returns_safe_reteach_fallback(self):
        diag = {
            "question_id": "cr-xyz",
            "curriculum_id": "nctb",
            "textbook_medium": "english_version",
            "class_level": 8,
            "subject": "science",
            "chapter": "Diffusion, Osmosis and Transpiration",
            "question_text": "Q?",
            "answer_language": "en",
            "options": [{"id": x, "text": x} for x in ("A", "B", "C", "D")],
            "correct_option": "A",
            "explanation": "Water crosses a semi-permeable membrane.",
            "misconception_labels": {"B": "Likely misconception: confusing diffusion with osmosis"},
            "source": {"chunk_id": 301, "textbook_medium": "english_version", "snippet": "Osmosis moves water."},
        }

        def failing_llm(*a, **k):
            raise RuntimeError("503 unavailable")

        res = concept_rescue.submit_diagnostic_answer(
            "sess-fail",
            diag,
            "B",
            event_key="evt-fail-1",
            answer_language="en",
            cfg=_cfg(),
            retrieve_fn=lambda *a, **k: EN_CHUNKS,
            llm_fn=failing_llm,
        )
        self.assertFalse(res["is_correct"])
        self.assertIn("Likely misconception:", res["likely_misconception"])
        self.assertIn("semi-permeable", res["reteach_explanation"])
        self.assertIsNone(res["follow_up_question"])


if __name__ == "__main__":
    unittest.main()
