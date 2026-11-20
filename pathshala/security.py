"""API security helpers: CORS origins, per-IP rate limiter, teacher token auth, and PII scrubbing."""
import os
import re
import time
from collections import defaultdict, deque

_PHONE_RE = re.compile(r"(?:\+?88[\s-]?)?01[3-9]\d{2}[\s-]?\d{6}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_BN_NAME_RE = re.compile(r"(আমার\s+নাম)\s+[^\s।,?!]+")
_EN_NAME_RE = re.compile(r"\b(my\s+name\s+is|i\s+am)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", re.IGNORECASE)


def scrub_pii(text: str) -> str:
    """Redact phone numbers, emails, and self-reported names before storing logs or analytics."""
    if not text:
        return ""
    s = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    s = _EMAIL_RE.sub("[REDACTED_EMAIL]", s)
    s = _BN_NAME_RE.sub(r"\1 [REDACTED_NAME]", s)
    s = _EN_NAME_RE.sub(r"\1 [REDACTED_NAME]", s)
    return s


def allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "https://web-xi-peach-30.vercel.app,http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


class RateLimiter:
    """In-memory per-IP sliding-window rate limiter (requests per 60s)."""

    def __init__(self, max_per_min: int = 60):
        self.max_per_min = max(1, int(max_per_min))
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, ip: str, now: float | None = None) -> bool:
        t = time.time() if now is None else now
        q = self._hits[ip or "unknown"]
        cutoff = t - 60.0
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= self.max_per_min:
            return False
        q.append(t)
        return True

    def clear(self):
        self._hits.clear()


def verify_teacher_token(provided: str | None, expected: str | None = None) -> bool:
    """If TEACHER_TOKEN is configured, require an exact match; if unset, allow open demo access."""
    secret = os.getenv("TEACHER_TOKEN", "").strip() if expected is None else (expected or "").strip()
    if not secret:
        return True
    return bool(provided) and provided.strip() == secret
