"""Anonymous session mastery tracking (EWMA per chapter, no PII)."""
from collections import defaultdict

# session_id -> {(class_level, subject, chapter): {"mastery": float, "attempts": int, "correct": int}}
_SESSIONS: dict[str, dict[tuple[int, str, str], dict]] = defaultdict(dict)


def update_ewma(prev: float, correct: bool, alpha: float = 0.35) -> float:
    """Exponentially weighted moving average mastery update in [0.0, 1.0]."""
    val = 1.0 if correct else 0.0
    return round(max(0.0, min(1.0, (1.0 - alpha) * prev + alpha * val)), 4)


def difficulty_for_mastery(score: float) -> str:
    """Map mastery score to adaptive practice difficulty level."""
    if score < 0.45:
        return "recall"
    if score < 0.75:
        return "understanding"
    return "application"


def record_attempt(session_id: str, class_level: int, subject: str, chapter: str, correct: bool) -> dict:
    sid = (session_id or "anon").strip()[:64] or "anon"
    key = (int(class_level), (subject or "general").strip(), (chapter or "অধ্যায়").strip())
    rec = _SESSIONS[sid].get(key, {"mastery": 0.5, "attempts": 0, "correct": 0})
    new_score = update_ewma(rec["mastery"], bool(correct))
    rec = {
        "mastery": new_score,
        "attempts": rec["attempts"] + 1,
        "correct": rec["correct"] + (1 if correct else 0),
        "difficulty": difficulty_for_mastery(new_score),
    }
    _SESSIONS[sid][key] = rec
    return {
        "class_level": key[0],
        "subject": key[1],
        "chapter": key[2],
        **rec,
    }


def get_session_mastery(session_id: str) -> dict:
    sid = (session_id or "anon").strip()[:64] or "anon"
    entries = []
    for (cls, subj, chap), rec in _SESSIONS.get(sid, {}).items():
        entries.append(
            {
                "class_level": cls,
                "subject": subj,
                "chapter": chap,
                "mastery": rec["mastery"],
                "attempts": rec["attempts"],
                "correct": rec["correct"],
                "difficulty": difficulty_for_mastery(rec["mastery"]),
            }
        )
    entries.sort(key=lambda x: x["mastery"])
    weak = [e for e in entries if e["mastery"] < 0.55]
    recommended = entries[0] if entries else None
    return {
        "session_id": sid,
        "chapters": entries,
        "weak_chapters": weak,
        "recommended_chapter": recommended,
    }


def get_aggregate_mastery() -> list[dict]:
    """Aggregate average mastery across anonymous sessions for teacher dashboard."""
    buckets: dict[tuple[int, str, str], list[float]] = defaultdict(list)
    for sess in _SESSIONS.values():
        for key, rec in sess.items():
            buckets[key].append(rec["mastery"])
    out = []
    for (cls, subj, chap), scores in buckets.items():
        avg = round(sum(scores) / len(scores), 4)
        out.append(
            {
                "class_level": cls,
                "subject": subj,
                "chapter": chap,
                "avg_mastery": avg,
                "sessions": len(scores),
                "difficulty": difficulty_for_mastery(avg),
            }
        )
    out.sort(key=lambda x: x["avg_mastery"])
    return out


def clear_all():
    _SESSIONS.clear()
