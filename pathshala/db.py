"""Postgres helpers (psycopg3). Logging is best-effort: never break an answer because logging failed."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

from .config import get_config
from .security import scrub_pii

_CATALOG_CACHE: dict[tuple[str, ...], tuple[float, list[dict]]] = {}
_CATALOG_TTL_SEC = 300.0


def clear_catalog_cache() -> None:
    """Clear the in-memory curriculum catalog cache across all shard sets."""
    _CATALOG_CACHE.clear()


def resolve_db_url(textbook_medium: str | None = None, class_level: int | None = None, cfg=None) -> str:
    """Route textbook queries to the proper DB shard:
    - ('english_version', any class) -> cfg.database_url_en
    - ('bangla_version', class >= 9) -> cfg.database_url_bn_ssc
    - ('bangla_version', class <= 8) / default -> cfg.database_url
    """
    cfg = cfg or get_config()
    med = (textbook_medium or "bangla_version").strip().lower()
    if med == "english_version":
        return cfg.database_url_en
    if med == "bangla_version" and class_level is not None and int(class_level) >= 9:
        return cfg.database_url_bn_ssc
    return cfg.database_url


def all_shard_urls(cfg=None) -> list[str]:
    """Unique database URLs across primary, Bangla SSC, and English shards (preserving order)."""
    cfg = cfg or get_config()
    urls = []
    for u in (cfg.database_url, cfg.database_url_bn_ssc, cfg.database_url_en):
        if u and u not in urls:
            urls.append(u)
    return urls


def get_conn(
    cfg=None,
    *,
    textbook_medium: str | None = None,
    class_level: int | None = None,
    db_url: str | None = None,
):
    import psycopg
    from psycopg.rows import dict_row

    cfg = cfg or get_config()
    target = db_url or resolve_db_url(textbook_medium, class_level, cfg)
    return psycopg.connect(target, row_factory=dict_row)


def apply_migrations(migrations_dir: Path | None = None, cfg=None) -> list[str]:
    """Execute base schema.sql and sorted SQL migration files idempotently across all DB shards."""
    root_db = Path(__file__).resolve().parent.parent / "db"
    schema_file = root_db / "schema.sql"
    mdir = migrations_dir or (root_db / "migrations")
    files = sorted(mdir.glob("*.sql"))
    applied = []
    for url in all_shard_urls(cfg):
        with get_conn(cfg, db_url=url) as c, c.cursor() as cur:
            if migrations_dir is None and schema_file.exists():
                cur.execute(schema_file.read_text(encoding="utf-8"))
                if "schema.sql" not in applied:
                    applied.append("schema.sql")
            for f in files:
                cur.execute(f.read_text(encoding="utf-8"))
                if f.name not in applied:
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


def merge_shard_books(shard_rows: list[tuple[str, list[dict]]], cfg=None) -> list[dict]:
    """Merge textbook rows across shards, preferring the authoritative shard for each textbook identity."""
    cfg = cfg or get_config()
    best: dict[tuple[str, str, int, str], tuple[bool, dict]] = {}
    for url, rows in shard_rows:
        for r in rows:
            d = dict(r)
            curr = d.get("curriculum_id") or "nctb"
            med = d.get("textbook_medium") or "bangla_version"
            cls = int(d.get("class_level") or 0)
            subj = d.get("subject") or ""
            key = (curr, med, cls, subj)
            is_auth = resolve_db_url(med, cls, cfg) == url
            if key not in best or (is_auth and not best[key][0]):
                best[key] = (is_auth, d)
    out = [v[1] for v in best.values()]
    out.sort(
        key=lambda x: (
            x.get("curriculum_id") or "nctb",
            x.get("textbook_medium") or "",
            int(x.get("class_level") or 0),
            x.get("subject") or "",
        )
    )
    return out


def _fetch_shard_catalog(url: str, cfg) -> tuple[str, list[dict]] | None:
    try:
        with get_conn(cfg, db_url=url) as c, c.cursor() as cur:
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
            return url, cur.fetchall()
    except Exception:
        return None


def get_curriculum_catalog(cfg=None, *, use_cache: bool = True) -> list[dict]:
    """Return available textbooks across all shards with chunk/embedding counts, excluding unknown medium."""
    cfg = cfg or get_config()
    urls = tuple(all_shard_urls(cfg))
    if use_cache and urls in _CATALOG_CACHE:
        ts, cached = _CATALOG_CACHE[urls]
        if (time.monotonic() - ts) < _CATALOG_TTL_SEC:
            return [dict(item) for item in cached]

    shard_rows: list[tuple[str, list[dict]]] = []
    if len(urls) <= 1:
        for url in urls:
            res = _fetch_shard_catalog(url, cfg)
            if res is not None:
                shard_rows.append(res)
    else:
        with ThreadPoolExecutor(max_workers=len(urls)) as executor:
            for res in executor.map(lambda u: _fetch_shard_catalog(u, cfg), urls):
                if res is not None:
                    shard_rows.append(res)

    merged = merge_shard_books(shard_rows, cfg=cfg)
    if use_cache and merged:
        _CATALOG_CACHE[urls] = (time.monotonic(), [dict(item) for item in merged])
    return merged


def is_curriculum_available(
    class_level: int,
    subject: str | None = None,
    textbook_medium: str = "bangla_version",
    curriculum_id: str = "nctb",
    cfg=None,
) -> bool:
    """True only if verified chunks exist on the target shard for the exact curriculum/medium/class/(subject)."""
    if textbook_medium not in ("bangla_version", "english_version"):
        return False
    with get_conn(cfg, textbook_medium=textbook_medium, class_level=class_level) as c, c.cursor() as cur:
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


def format_teacher_summary(
    totals: dict | None,
    chapters: list[dict],
    top_questions: list[dict],
    concept_gaps: list[dict] | None = None,
    misconceptions: list[dict] | None = None,
    min_group_size: int = 3,
) -> dict:
    """Format SQL aggregates into teacher summary payload with rates, Concept Rescue gaps & privacy suppression."""
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

    suppressed = 0
    fmt_gaps = []
    for g in concept_gaps or []:
        attempts = int(g.get("attempts") or 0)
        incorrect = int(g.get("incorrect_count") or 0)
        seed_a = int(g.get("seed_attempts") or 0)
        real_a = int(g.get("real_attempts") or 0)
        uniq = int(g.get("unique_sessions") or 0)
        if real_a > 0 and seed_a == 0 and uniq < min_group_size:
            suppressed += 1
            continue
        fmt_gaps.append(
            {
                "curriculum_id": g.get("curriculum_id") or "nctb",
                "textbook_medium": g.get("textbook_medium") or "bangla_version",
                "class_level": int(g.get("class_level") or 0),
                "subject": g.get("subject") or "general",
                "chapter": g.get("chapter") or "",
                "attempts": attempts,
                "incorrect_count": incorrect,
                "incorrect_rate": round(incorrect / attempts, 4) if attempts > 0 else 0.0,
                "seed_attempts": seed_a,
                "real_attempts": real_a,
                "unique_sessions": uniq,
                "avg_mastery": round(float(g.get("avg_mastery") or 0.5), 4),
                "low_sample_warning": attempts < min_group_size,
                "is_demo_data": seed_a > 0 and real_a == 0,
            }
        )

    fmt_misc = []
    for m in misconceptions or []:
        cnt = int(m.get("count") or 0)
        seed_c = int(m.get("seed_count") or 0)
        real_c = int(m.get("real_count") or 0)
        uniq = int(m.get("unique_sessions") or 0)
        if real_c > 0 and seed_c == 0 and uniq < min_group_size:
            suppressed += 1
            continue
        fmt_misc.append(
            {
                "likely_misconception": m.get("likely_misconception") or "",
                "textbook_medium": m.get("textbook_medium") or "bangla_version",
                "class_level": int(m.get("class_level") or 0),
                "subject": m.get("subject") or "general",
                "chapter": m.get("chapter") or "",
                "count": cnt,
                "seed_count": seed_c,
                "real_count": real_c,
                "is_demo_data": seed_c > 0 and real_c == 0,
            }
        )

    return {
        "total_queries": total_q,
        "seed_queries": seed_q,
        "real_queries": real_q,
        "refused_queries": refused_q,
        "refusal_rate": round(refused_q / total_q, 4) if total_q > 0 else 0.0,
        "feedback_count": fb_count,
        "helpful_count": helpful_c,
        "helpful_rate": round(helpful_c / fb_count, 4) if fb_count > 0 else 0.0,
        "has_seed_data": seed_q > 0 or any(g["seed_attempts"] > 0 for g in fmt_gaps),
        "privacy_threshold_min_sessions": min_group_size,
        "suppressed_small_groups": suppressed,
        "chapters": fmt_chapters,
        "top_questions": fmt_top,
        "concept_gaps": fmt_gaps,
        "recurring_misconceptions": fmt_misc,
    }


def teacher_summary(limit: int = 50, min_group_size: int = 3) -> dict:
    """Return chapter counts, refusal & helpful rates, top questions, and Concept Rescue learning gaps."""
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

        concept_gaps, misconceptions = [], []
        try:
            cur.execute(
                """with m as (
                       select curriculum_id, textbook_medium, class_level, subject, chapter,
                              round(avg(mastery)::numeric, 4)::float as avg_mastery
                       from session_mastery
                       group by 1, 2, 3, 4, 5
                   )
                   select le.curriculum_id, le.textbook_medium, le.class_level, le.subject, le.chapter,
                          count(*) as attempts,
                          coalesce(sum(case when not le.is_correct then 1 else 0 end), 0) as incorrect_count,
                          coalesce(sum(case when le.session_id = 'seed' then 1 else 0 end), 0) as seed_attempts,
                          coalesce(sum(case when le.session_id is distinct from 'seed' then 1 else 0 end), 0) as real_attempts,
                          count(distinct le.session_id) as unique_sessions,
                          coalesce(max(m.avg_mastery), 0.5) as avg_mastery
                   from learning_events le
                   left join m on m.curriculum_id = le.curriculum_id
                              and m.textbook_medium = le.textbook_medium
                              and m.class_level = le.class_level
                              and m.subject = le.subject
                              and m.chapter = le.chapter
                   group by 1, 2, 3, 4, 5
                   order by incorrect_count desc, attempts desc
                   limit %s""",
                (limit,),
            )
            concept_gaps = cur.fetchall()

            cur.execute(
                """select likely_misconception, textbook_medium, class_level, subject, chapter,
                          count(*) as count,
                          coalesce(sum(case when session_id = 'seed' then 1 else 0 end), 0) as seed_count,
                          coalesce(sum(case when session_id is distinct from 'seed' then 1 else 0 end), 0) as real_count,
                          count(distinct session_id) as unique_sessions
                   from learning_events
                   where not is_correct and likely_misconception is not null and trim(likely_misconception) <> ''
                   group by 1, 2, 3, 4, 5
                   order by count desc
                   limit 15"""
            )
            misconceptions = cur.fetchall()
        except Exception:
            concept_gaps, misconceptions = [], []

    return format_teacher_summary(
        totals,
        chapters,
        top_questions,
        concept_gaps=concept_gaps,
        misconceptions=misconceptions,
        min_group_size=min_group_size,
    )


def _infer_shard_from_ref(chunk_ref: str | None) -> tuple[str | None, int | None]:
    if not chunk_ref:
        return None, None
    ref = chunk_ref.strip()
    med = "english_version" if ref.startswith("en-") else "bangla_version"
    raw = ref[3:] if ref.startswith("en-") else ref
    head = raw.split("-", 1)[0]
    cls = int(head) if head.isdigit() else None
    return med, cls


def get_chunk(
    chunk_id: int,
    *,
    textbook_medium: str | None = None,
    class_level: int | None = None,
    chunk_ref: str | None = None,
    cfg=None,
) -> dict | None:
    cfg = cfg or get_config()
    if textbook_medium is None and chunk_ref:
        textbook_medium, inferred_cls = _infer_shard_from_ref(chunk_ref)
        if class_level is None:
            class_level = inferred_cls

    urls = all_shard_urls(cfg)
    if textbook_medium is not None or class_level is not None:
        preferred = resolve_db_url(textbook_medium, class_level, cfg)
        urls = [preferred] + [u for u in urls if u != preferred]

    sql_by_ref = """select c.id, c.chunk_ref, c.text, c.chapter_no, c.chapter, c.page_start, c.page_end,
                           t.title as book, t.curriculum_id, t.textbook_medium, t.edition_year, t.class_level, t.subject
                    from chunks c join textbooks t on t.id=c.textbook_id where c.chunk_ref=%s"""
    sql_by_id = """select c.id, c.chunk_ref, c.text, c.chapter_no, c.chapter, c.page_start, c.page_end,
                          t.title as book, t.curriculum_id, t.textbook_medium, t.edition_year, t.class_level, t.subject
                   from chunks c join textbooks t on t.id=c.textbook_id where c.id=%s"""

    for url in urls:
        try:
            with get_conn(cfg, db_url=url) as c, c.cursor() as cur:
                if chunk_ref:
                    cur.execute(sql_by_ref, (chunk_ref,))
                    row = cur.fetchone()
                    if row:
                        return row
                cur.execute(sql_by_id, (chunk_id,))
                row = cur.fetchone()
                if row:
                    return row
        except Exception:
            continue
    return None


def get_chapter(
    book_id: int,
    chapter_no: int,
    *,
    textbook_medium: str | None = None,
    class_level: int | None = None,
    cfg=None,
) -> list[dict]:
    cfg = cfg or get_config()
    urls = all_shard_urls(cfg)
    if textbook_medium is not None or class_level is not None:
        preferred = resolve_db_url(textbook_medium, class_level, cfg)
        urls = [preferred] + [u for u in urls if u != preferred]
    for url in urls:
        try:
            with get_conn(cfg, db_url=url) as c, c.cursor() as cur:
                cur.execute(
                    "select id, chunk_ref, text, chapter_no, chapter, page_start, page_end from chunks where textbook_id=%s and chapter_no=%s order by id",
                    (book_id, chapter_no),
                )
                rows = cur.fetchall()
                if rows:
                    return rows
        except Exception:
            continue
    return []


def list_chapters(
    book_id: int,
    *,
    textbook_medium: str | None = None,
    class_level: int | None = None,
    cfg=None,
) -> list[dict]:
    cfg = cfg or get_config()
    urls = all_shard_urls(cfg)
    if textbook_medium is not None or class_level is not None:
        preferred = resolve_db_url(textbook_medium, class_level, cfg)
        urls = [preferred] + [u for u in urls if u != preferred]
    for url in urls:
        try:
            with get_conn(cfg, db_url=url) as c, c.cursor() as cur:
                cur.execute(
                    "select chapter_no, chapter, min(page_start) as page_start, max(page_end) as page_end, count(*) as chunks from chunks where textbook_id=%s group by chapter_no, chapter order by chapter_no",
                    (book_id,),
                )
                rows = cur.fetchall()
                if rows:
                    return rows
        except Exception:
            continue
    return []


def list_books(cfg=None) -> list[dict]:
    cfg = cfg or get_config()
    shard_rows: list[tuple[str, list[dict]]] = []
    for url in all_shard_urls(cfg):
        try:
            with get_conn(cfg, db_url=url) as c, c.cursor() as cur:
                cur.execute(
                    "select id, title, curriculum_id, textbook_medium, edition_year, class_level, subject from textbooks order by curriculum_id, textbook_medium, class_level, subject"
                )
                shard_rows.append((url, cur.fetchall()))
        except Exception:
            continue
    return merge_shard_books(shard_rows, cfg=cfg)
