"""Anonymous session mastery tracking (EWMA per chapter + Postgres persistence, no PII)."""
import csv
import io
from collections import defaultdict

# session_id -> {(curriculum_id, textbook_medium, class_level, subject, chapter): {...}}
_SESSIONS: dict[str, dict[tuple[str, str, int, str, str], dict]] = defaultdict(dict)
_SEEN_EVENT_KEYS: set[str] = set()
INDICATOR_LABEL = "estimated_practice_mastery"


def update_ewma(prev: float, correct: bool, alpha: float = 0.35) -> float:
    """Exponentially weighted moving average practice mastery estimate in [0.0, 1.0]."""
    val = 1.0 if correct else 0.0
    return round(max(0.0, min(1.0, (1.0 - alpha) * prev + alpha * val)), 4)


def difficulty_for_mastery(score: float) -> str:
    """Map mastery estimate to adaptive practice difficulty level."""
    if score < 0.45:
        return "recall"
    if score < 0.75:
        return "understanding"
    return "application"


def _norm_key(
    session_id: str,
    class_level: int,
    subject: str | None,
    chapter: str,
    curriculum_id: str = "nctb",
    textbook_medium: str = "bangla_version",
):
    sid = (session_id or "anon").strip()[:64] or "anon"
    curr = (curriculum_id or "nctb").strip().lower() or "nctb"
    med = (textbook_medium or "bangla_version").strip().lower() or "bangla_version"
    cls = int(class_level)
    subj = (subject or "general").strip() or "general"
    chap = (chapter or "অধ্যায়").strip() or "অধ্যায়"
    return sid, (curr, med, cls, subj, chap)


def record_attempt(
    session_id: str,
    class_level: int,
    subject: str,
    chapter: str,
    correct: bool,
    *,
    curriculum_id: str = "nctb",
    textbook_medium: str = "bangla_version",
    event_key: str | None = None,
    learning_objective: str | None = None,
    event_type: str = "practice_attempt",
    question_id: str | None = None,
    selected_option: str | None = None,
    likely_misconception: str | None = None,
    use_db: bool = False,
) -> dict:
    """Record a learning attempt and update EWMA mastery with optional Postgres persistence & idempotency."""
    sid, key = _norm_key(session_id, class_level, subject, chapter, curriculum_id, textbook_medium)
    curr, med, cls, subj, chap = key
    clean_ek = (event_key or "").strip()[:120] or None

    if clean_ek and clean_ek in _SEEN_EVENT_KEYS:
        existing = _SESSIONS[sid].get(key, {"mastery": 0.5, "attempts": 0, "correct": 0})
        return {
            "curriculum_id": curr,
            "textbook_medium": med,
            "class_level": cls,
            "subject": subj,
            "chapter": chap,
            "difficulty": difficulty_for_mastery(existing["mastery"]),
            "indicator_label": INDICATOR_LABEL,
            "duplicate": True,
            **existing,
        }

    if use_db:
        try:
            db_res = _record_db(
                sid,
                curr,
                med,
                cls,
                subj,
                chap,
                bool(correct),
                clean_ek,
                learning_objective,
                event_type,
                question_id,
                selected_option,
                likely_misconception,
            )
            if clean_ek:
                _SEEN_EVENT_KEYS.add(clean_ek)
            _SESSIONS[sid][key] = {
                "mastery": db_res["mastery"],
                "attempts": db_res["attempts"],
                "correct": db_res["correct"],
                "difficulty": db_res["difficulty"],
            }
            return db_res
        except Exception:
            pass

    rec = _SESSIONS[sid].get(key, {"mastery": 0.5, "attempts": 0, "correct": 0})
    new_score = update_ewma(rec["mastery"], bool(correct))
    rec = {
        "mastery": new_score,
        "attempts": rec["attempts"] + 1,
        "correct": rec["correct"] + (1 if correct else 0),
        "difficulty": difficulty_for_mastery(new_score),
    }
    _SESSIONS[sid][key] = rec
    if clean_ek:
        _SEEN_EVENT_KEYS.add(clean_ek)
    return {
        "curriculum_id": curr,
        "textbook_medium": med,
        "class_level": cls,
        "subject": subj,
        "chapter": chap,
        "indicator_label": INDICATOR_LABEL,
        "duplicate": False,
        **rec,
    }


def _record_db(
    sid: str,
    curr: str,
    med: str,
    cls: int,
    subj: str,
    chap: str,
    correct: bool,
    event_key: str | None,
    learning_objective: str | None,
    event_type: str,
    question_id: str | None,
    selected_option: str | None,
    likely_misconception: str | None,
) -> dict:
    from .db import get_conn

    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """select mastery, attempts, correct
               from session_mastery
               where session_id=%s and curriculum_id=%s and textbook_medium=%s
                 and class_level=%s and subject=%s and chapter=%s
               for update""",
            (sid, curr, med, cls, subj, chap),
        )
        prev = cur.fetchone() or {"mastery": 0.5, "attempts": 0, "correct": 0}

        if event_key:
            cur.execute(
                """insert into learning_events(
                       event_key, session_id, curriculum_id, textbook_medium, class_level, subject, chapter,
                       learning_objective, event_type, question_id, selected_option, is_correct, likely_misconception
                   ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   on conflict (event_key) do nothing
                   returning id""",
                (event_key, sid, curr, med, cls, subj, chap, learning_objective, event_type, question_id, selected_option, correct, likely_misconception),
            )
            inserted = cur.fetchone()
            if inserted is None:
                m_val = float(prev["mastery"])
                return {
                    "curriculum_id": curr,
                    "textbook_medium": med,
                    "class_level": cls,
                    "subject": subj,
                    "chapter": chap,
                    "mastery": m_val,
                    "attempts": int(prev["attempts"]),
                    "correct": int(prev["correct"]),
                    "difficulty": difficulty_for_mastery(m_val),
                    "indicator_label": INDICATOR_LABEL,
                    "duplicate": True,
                }
        else:
            cur.execute(
                """insert into learning_events(
                       session_id, curriculum_id, textbook_medium, class_level, subject, chapter,
                       learning_objective, event_type, question_id, selected_option, is_correct, likely_misconception
                   ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (sid, curr, med, cls, subj, chap, learning_objective, event_type, question_id, selected_option, correct, likely_misconception),
            )

        new_score = update_ewma(float(prev["mastery"]), correct)
        new_attempts = int(prev["attempts"]) + 1
        new_correct = int(prev["correct"]) + (1 if correct else 0)
        cur.execute(
            """insert into session_mastery(
                   session_id, curriculum_id, textbook_medium, class_level, subject, chapter,
                   mastery, attempts, correct, last_misconception, updated_at
               ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
               on conflict (session_id, curriculum_id, textbook_medium, class_level, subject, chapter) do update set
                 mastery=excluded.mastery,
                 attempts=excluded.attempts,
                 correct=excluded.correct,
                 last_misconception=coalesce(excluded.last_misconception, session_mastery.last_misconception),
                 updated_at=now()""",
            (sid, curr, med, cls, subj, chap, new_score, new_attempts, new_correct, likely_misconception),
        )
        return {
            "curriculum_id": curr,
            "textbook_medium": med,
            "class_level": cls,
            "subject": subj,
            "chapter": chap,
            "mastery": new_score,
            "attempts": new_attempts,
            "correct": new_correct,
            "difficulty": difficulty_for_mastery(new_score),
            "indicator_label": INDICATOR_LABEL,
            "duplicate": False,
        }


def get_session_mastery(session_id: str, *, use_db: bool = False) -> dict:
    sid = (session_id or "anon").strip()[:64] or "anon"
    entries = []
    if use_db:
        try:
            from .db import get_conn

            with get_conn() as c, c.cursor() as cur:
                cur.execute(
                    """select curriculum_id, textbook_medium, class_level, subject, chapter,
                              mastery, attempts, correct, last_misconception
                       from session_mastery
                       where session_id = %s
                       order by mastery asc""",
                    (sid,),
                )
                for row in cur.fetchall():
                    m_val = float(row["mastery"])
                    entries.append(
                        {
                            "curriculum_id": row["curriculum_id"],
                            "textbook_medium": row["textbook_medium"],
                            "class_level": int(row["class_level"]),
                            "subject": row["subject"],
                            "chapter": row["chapter"],
                            "mastery": m_val,
                            "attempts": int(row["attempts"]),
                            "correct": int(row["correct"]),
                            "last_misconception": row.get("last_misconception"),
                            "difficulty": difficulty_for_mastery(m_val),
                        }
                    )
        except Exception:
            entries = []

    if not entries:
        for (curr, med, cls, subj, chap), rec in _SESSIONS.get(sid, {}).items():
            entries.append(
                {
                    "curriculum_id": curr,
                    "textbook_medium": med,
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
        "indicator_label": INDICATOR_LABEL,
        "note": "Estimated practice mastery indicator (EWMA), not a definitive measure of understanding.",
        "chapters": entries,
        "weak_chapters": weak,
        "recommended_chapter": recommended,
    }


def get_aggregate_mastery(*, use_db: bool = False) -> list[dict]:
    """Aggregate average practice mastery across anonymous sessions for teacher dashboard."""
    if use_db:
        try:
            from .db import get_conn

            with get_conn() as c, c.cursor() as cur:
                cur.execute(
                    """select curriculum_id, textbook_medium, class_level, subject, chapter,
                              round(avg(mastery)::numeric, 4)::float as avg_mastery,
                              count(distinct session_id) as sessions
                       from session_mastery
                       group by curriculum_id, textbook_medium, class_level, subject, chapter
                       order by avg_mastery asc"""
                )
                rows = cur.fetchall()
                if rows:
                    return [
                        {
                            "curriculum_id": r["curriculum_id"],
                            "textbook_medium": r["textbook_medium"],
                            "class_level": int(r["class_level"]),
                            "subject": r["subject"],
                            "chapter": r["chapter"],
                            "avg_mastery": float(r["avg_mastery"]),
                            "sessions": int(r["sessions"]),
                            "difficulty": difficulty_for_mastery(float(r["avg_mastery"])),
                        }
                        for r in rows
                    ]
        except Exception:
            pass

    buckets: dict[tuple[str, str, int, str, str], list[float]] = defaultdict(list)
    for sess in _SESSIONS.values():
        for key, rec in sess.items():
            buckets[key].append(rec["mastery"])
    out = []
    for (curr, med, cls, subj, chap), scores in buckets.items():
        avg = round(sum(scores) / len(scores), 4)
        out.append(
            {
                "curriculum_id": curr,
                "textbook_medium": med,
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


def delete_session(session_id: str, *, use_db: bool = False) -> dict:
    """Erase anonymous session progress & queries per retention/deletion policy."""
    sid = (session_id or "anon").strip()[:64] or "anon"
    in_mem = 1 if sid in _SESSIONS else 0
    _SESSIONS.pop(sid, None)
    db_deleted = {"learning_events": 0, "session_mastery": 0, "queries": 0}
    if use_db:
        try:
            from .db import get_conn

            with get_conn() as c, c.cursor() as cur:
                for tbl in ("learning_events", "session_mastery", "queries"):
                    cur.execute(f"delete from {tbl} where session_id = %s", (sid,))
                    db_deleted[tbl] = cur.rowcount or 0
        except Exception:
            pass
    return {"session_id": sid, "cleared_memory": in_mem, **db_deleted}


def clear_all():
    _SESSIONS.clear()
    _SEEN_EVENT_KEYS.clear()


def weak_chapters_csv(*, use_db: bool = False) -> str:
    """Export aggregated chapter mastery sorted weakest-first as CSV for teacher assignments."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["class_level", "subject", "chapter", "avg_mastery", "sessions", "recommended_difficulty"])
    for row in get_aggregate_mastery(use_db=use_db):
        w.writerow(
            [
                row["class_level"],
                row["subject"],
                row["chapter"],
                row["avg_mastery"],
                row["sessions"],
                row["difficulty"],
            ]
        )
    return buf.getvalue()
