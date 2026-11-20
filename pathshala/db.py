"""Postgres helpers (psycopg3). Logging is best-effort: never break an answer because logging failed."""
from pathlib import Path

from .config import get_config
from .security import scrub_pii


def get_conn(cfg=None):
    import psycopg
    from psycopg.rows import dict_row

    cfg = cfg or get_config()
    return psycopg.connect(cfg.database_url, row_factory=dict_row)


def apply_migrations(migrations_dir: Path | None = None, cfg=None) -> list[str]:
    """Execute sorted SQL migration files idempotently."""
    mdir = migrations_dir or (Path(__file__).resolve().parent.parent / "db" / "migrations")
    files = sorted(mdir.glob("*.sql"))
    applied = []
    with get_conn(cfg) as c, c.cursor() as cur:
        for f in files:
            cur.execute(f.read_text(encoding="utf-8"))
            applied.append(f.name)
    return applied


def log_query(rec: dict):
    if rec.get("reason") == "safety_distress":
        return None
    payload = {
        "curriculum_id": "nctb",
        "textbook_medium": "bangla_version",
        "answer_language": "bn",
        **rec,
        "question": scrub_pii(rec.get("question") or "")[:600],
    }
    try:
        with get_conn() as c, c.cursor() as cur:
            cur.execute(
                """insert into queries(session_id,curriculum_id,textbook_medium,answer_language,class_level,subject,question,topic,top_score,refused,reason,latency_ms,cost_usd)
                   values (%(session_id)s,%(curriculum_id)s,%(textbook_medium)s,%(answer_language)s,%(class_level)s,%(subject)s,%(question)s,%(topic)s,%(top_score)s,%(refused)s,%(reason)s,%(latency_ms)s,%(cost_usd)s)
                   returning id""",
                payload,
            )
            return cur.fetchone()["id"]
    except Exception:
        return None


def log_feedback(query_id: int, helpful: bool, comment: str | None = None) -> bool:
    try:
        with get_conn() as c, c.cursor() as cur:
            cur.execute("insert into feedback(query_id,helpful,comment) values (%s,%s,%s)", (query_id, helpful, comment))
        return True
    except Exception:
        return False


def get_curriculum_catalog(cfg=None) -> list[dict]:
    """Return available textbooks with chunk/embedding counts, excluding unknown medium."""
    with get_conn(cfg) as c, c.cursor() as cur:
        cur.execute(
            """select t.id, t.curriculum_id, t.textbook_medium, t.edition_year, t.class_level, t.subject,
                      t.title, t.source, t.source_license,
                      count(c.id) as chunk_count,
                      count(c.embedding) as embedded_count
               from textbooks t
               join chunks c on c.textbook_id = t.id
               where t.textbook_medium in ('bangla_version', 'english_version')
               group by t.id
               having count(c.id) > 0
               order by t.curriculum_id, t.textbook_medium, t.class_level, t.subject"""
        )
        return cur.fetchall()


def is_curriculum_available(
    class_level: int,
    subject: str | None = None,
    textbook_medium: str = "bangla_version",
    curriculum_id: str = "nctb",
    cfg=None,
) -> bool:
    """True only if verified chunks exist for the exact curriculum/medium/class/(subject)."""
    if textbook_medium not in ("bangla_version", "english_version"):
        return False
    with get_conn(cfg) as c, c.cursor() as cur:
        cur.execute(
            """select exists (
                   select 1
                   from textbooks t
                   join chunks c on c.textbook_id = t.id
                   where t.curriculum_id = %(curr)s
                     and t.textbook_medium = %(med)s
                     and t.class_level = %(cl)s
                     and (%(subj)s::text is null or t.subject = %(subj)s)
               ) as ok""",
            {"curr": curriculum_id, "med": textbook_medium, "cl": int(class_level), "subj": subject},
        )
        row = cur.fetchone()
        return bool(row and row.get("ok"))


def topic_counts(limit: int = 50) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """select class_level, subject, topic, count(*) as n, sum(case when refused then 1 else 0 end) as refused
               from queries where topic is not null group by 1,2,3 order by n desc limit %s""",
            (limit,),
        )
        return cur.fetchall()


def format_teacher_summary(totals: dict | None, chapters: list[dict], top_questions: list[dict]) -> dict:
    """Format SQL aggregates into teacher summary payload with safe rates and seed/real counts."""
    t = totals or {}
    total_q = int(t.get("total_queries") or 0)
    seed_q = int(t.get("seed_queries") or 0)
    real_q = int(t.get("real_queries") or 0)
    refused_q = int(t.get("refused_queries") or 0)
    fb_count = int(t.get("feedback_count") or 0)
    helpful_c = int(t.get("helpful_count") or 0)

    fmt_chapters = []
    for ch in chapters:
        n = int(ch.get("n") or 0)
        ref = int(ch.get("refused") or 0)
        ch_fb = int(ch.get("feedback_count") or 0)
        ch_help = int(ch.get("helpful_count") or 0)
        fmt_chapters.append(
            {
                **ch,
                "n": n,
                "refused": ref,
                "seed_n": int(ch.get("seed_n") or 0),
                "real_n": int(ch.get("real_n") or 0),
                "feedback_count": ch_fb,
                "helpful_count": ch_help,
                "refusal_rate": round(ref / n, 4) if n > 0 else 0.0,
                "helpful_rate": round(ch_help / ch_fb, 4) if ch_fb > 0 else 0.0,
            }
        )

    fmt_top = [
        {
            **q,
            "n": int(q.get("n") or 0),
            "refused": int(q.get("refused") or 0),
            "seed_n": int(q.get("seed_n") or 0),
        }
        for q in top_questions
    ]

    return {
        "total_queries": total_q,
        "seed_queries": seed_q,
        "real_queries": real_q,
        "refused_queries": refused_q,
        "refusal_rate": round(refused_q / total_q, 4) if total_q > 0 else 0.0,
        "feedback_count": fb_count,
        "helpful_count": helpful_c,
        "helpful_rate": round(helpful_c / fb_count, 4) if fb_count > 0 else 0.0,
        "has_seed_data": seed_q > 0,
        "chapters": fmt_chapters,
        "top_questions": fmt_top,
    }


def teacher_summary(limit: int = 50) -> dict:
    """Return chapter counts, refusal & helpful rates, and top 10 repeated questions."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """select
                   count(*) as total_queries,
                   coalesce(sum(case when session_id = 'seed' then 1 else 0 end), 0) as seed_queries,
                   coalesce(sum(case when session_id is distinct from 'seed' then 1 else 0 end), 0) as real_queries,
                   coalesce(sum(case when refused then 1 else 0 end), 0) as refused_queries,
                   (select count(*) from feedback) as feedback_count,
                   (select coalesce(sum(case when helpful then 1 else 0 end), 0) from feedback) as helpful_count
               from queries"""
        )
        totals = cur.fetchone()

        cur.execute(
            """with fb as (
                   select query_id, count(*) as fb_n, sum(case when helpful then 1 else 0 end) as helpful_n
                   from feedback group by query_id
               )
               select q.class_level, q.subject, q.topic,
                      count(*) as n,
                      coalesce(sum(case when q.refused then 1 else 0 end), 0) as refused,
                      coalesce(sum(case when q.session_id = 'seed' then 1 else 0 end), 0) as seed_n,
                      coalesce(sum(case when q.session_id is distinct from 'seed' then 1 else 0 end), 0) as real_n,
                      coalesce(sum(fb.fb_n), 0) as feedback_count,
                      coalesce(sum(fb.helpful_n), 0) as helpful_count
               from queries q
               left join fb on fb.query_id = q.id
               where q.topic is not null
               group by 1, 2, 3
               order by n desc
               limit %s""",
            (limit,),
        )
        chapters = cur.fetchall()

        cur.execute(
            """select min(question) as question,
                      max(class_level) as class_level,
                      max(subject) as subject,
                      max(topic) as topic,
                      count(*) as n,
                      coalesce(sum(case when refused then 1 else 0 end), 0) as refused,
                      coalesce(sum(case when session_id = 'seed' then 1 else 0 end), 0) as seed_n
               from queries
               where question is not null and trim(question) <> ''
               group by lower(trim(regexp_replace(question, '\\s+', ' ', 'g')))
               order by n desc, 1 asc
               limit 10"""
        )
        top_questions = cur.fetchall()

    return format_teacher_summary(totals, chapters, top_questions)


def get_chunk(chunk_id: int) -> dict | None:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """select c.id, c.chunk_ref, c.text, c.chapter_no, c.chapter, c.page_start, c.page_end,
                      t.title as book, t.curriculum_id, t.textbook_medium, t.edition_year, t.class_level, t.subject
               from chunks c join textbooks t on t.id=c.textbook_id where c.id=%s""",
            (chunk_id,),
        )
        return cur.fetchone()


def get_chapter(book_id: int, chapter_no: int) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            "select id, chunk_ref, text, chapter_no, chapter, page_start, page_end from chunks where textbook_id=%s and chapter_no=%s order by id",
            (book_id, chapter_no),
        )
        return cur.fetchall()


def list_chapters(book_id: int) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            "select chapter_no, chapter, min(page_start) as page_start, max(page_end) as page_end, count(*) as chunks from chunks where textbook_id=%s group by chapter_no, chapter order by chapter_no",
            (book_id,),
        )
        return cur.fetchall()


def list_books() -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            "select id, title, curriculum_id, textbook_medium, edition_year, class_level, subject from textbooks order by curriculum_id, textbook_medium, class_level, subject"
        )
        return cur.fetchall()
