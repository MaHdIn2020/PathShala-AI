import unittest

from pathshala.security import RateLimiter, allowed_origins, verify_teacher_token


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


if __name__ == "__main__":
    unittest.main()
