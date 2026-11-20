import unittest
from unittest.mock import patch

from pathshala import db
from pathshala.security import RateLimiter, allowed_origins, scrub_pii, verify_teacher_token


class TestSecurity(unittest.TestCase):
    def test_rate_limiter_blocks_after_limit_and_recovers(self):
        rl = RateLimiter(max_per_min=3)
        self.assertTrue(rl.allow("1.2.3.4", now=100.0))
        self.assertTrue(rl.allow("1.2.3.4", now=110.0))
        self.assertTrue(rl.allow("1.2.3.4", now=120.0))
        self.assertFalse(rl.allow("1.2.3.4", now=130.0))
        # Different IP still allowed
        self.assertTrue(rl.allow("5.6.7.8", now=130.0))
        # After 60s window passes, allowed again
        self.assertTrue(rl.allow("1.2.3.4", now=161.0))

    def test_teacher_token_verification(self):
        self.assertTrue(verify_teacher_token(None, expected=""))
        self.assertFalse(verify_teacher_token(None, expected="secret123"))
        self.assertFalse(verify_teacher_token("wrong", expected="secret123"))
        self.assertTrue(verify_teacher_token("secret123", expected="secret123"))

    def test_allowed_origins_default_not_wildcard(self):
        origins = allowed_origins()
        self.assertNotIn("*", origins)
        self.assertTrue(len(origins) >= 1)

    def test_scrub_pii_redacts_phones_emails_and_names(self):
        raw = "My name is Rahim and call 01712345678 or +8801812345678 or rahim@example.com"
        clean = scrub_pii(raw)
        self.assertNotIn("01712345678", clean)
        self.assertNotIn("01812345678", clean)
        self.assertNotIn("rahim@example.com", clean)
        self.assertNotIn("Rahim", clean)
        self.assertIn("[REDACTED_PHONE]", clean)
        self.assertIn("[REDACTED_EMAIL]", clean)

        bn_clean = scrub_pii("আমার নাম তানভীর, আমার প্রশ্ন পানি কী?")
        self.assertNotIn("তানভীর", bn_clean)
        self.assertIn("[REDACTED_NAME]", bn_clean)

    @patch("pathshala.db.get_conn")
    def test_distress_queries_are_never_logged_to_db(self, mock_conn):
        res = db.log_query({"question": "আমি মরে যেতে চাই", "reason": "safety_distress"})
        self.assertIsNone(res)
        mock_conn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
