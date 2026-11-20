"""Hybrid retrieval: pgvector cosine + Postgres FTS, fused with RRF. Strictly isolated by curriculum & textbook_medium."""
import re

from . import embed as _embed
from .config import get_config
from .text import normalize_for_retrieval

_STOP = {
    "কী", "কি", "কেন", "কীভাবে", "কিভাবে", "কাকে", "বলে", "হয়", "হয়", "করো", "বলো", "লেখো", "দাও", "কোন", "কত",
    "the", "is", "are", "was", "were", "what", "how", "why", "who", "where", "when", "does", "do", "to", "a", "an", "in", "of",
}


def fts_terms(text: str) -> list[str]:
    """Extract clean Bangla/English search terms for FTS queries."""
    raw = [t for t in re.sub(r"[^\w\u0980-\u09FF]+", " ", (text or "").lower()).split() if len(t) >= 2]
    filtered = [t for t in raw if t not in _STOP]
    return list(dict.fromkeys(filtered or raw))[:10]


def fts_or_query(text: str) -> str:
    """Build a Postgres 'simple' OR tsquery string from clean terms."""
    return " | ".join(fts_terms(text))


def lexical_sim(terms: list[str], hay: str) -> float:
    """Calibrated lexical similarity in [0.0, 0.92] when a chunk has no embedding vector."""
    if not terms:
        return 0.0
    low = (hay or "").lower()
    hits = sum(1 for t in terms if t in low)
    if not hits:
        return 0.0
    if len(terms) >= 3 and hits == 1:
        return 0.41
    return min(0.92, round(0.42 + 0.48 * (hits / max(1, len(terms))), 4))


def rrf(rank_lists, k: int = 60, top: int | None = None):
    """Reciprocal Rank Fusion. rank_lists: list of ordered id lists. Returns [(id, score)] best first."""
    scores: dict = {}
    for lst in rank_lists:
        for r, i in enumerate(lst):
            scores[i] = scores.get(i, 0.0) + 1.0 / (k + r + 1)
    out = sorted(scores.items(), key=lambda x: (-x[1], str(x[0])))
    return out[:top] if top else out


_COLS = (
    "c.id, c.chunk_ref, c.text, c.contextual_text, c.chapter_no, c.chapter, c.page_start, c.page_end, "
    "t.title as book, t.id as book_id, t.curriculum_id, t.textbook_medium, t.edition_year, t.class_level, t.subject"
)
_FILTER = (
    "t.curriculum_id = %(curr)s and t.textbook_medium = %(med)s "
    "and t.class_level = %(cl)s and (%(subj)s::text is null or t.subject = %(subj)s)"
)


def fts_search(
    question: str,
    class_level: int,
    subject: str | None,
    k: int = 30,
    cfg=None,
    *,
    curriculum_id: str = "nctb",
    textbook_medium: str = "bangla_version",
) -> list[dict]:
    """Low-RAM Postgres FTS-only retrieval scoped strictly to curriculum_id & textbook_medium."""
    from .db import get_conn

    cfg = cfg or get_config()
    norm_q = normalize_for_retrieval(question)
    terms = fts_terms(norm_q)
    tsq = " | ".join(terms)
    if not tsq:
        return []
    p = {"curr": curriculum_id, "med": textbook_medium, "cl": class_level, "subj": subject, "tsq": tsq, "k": k}
    with get_conn(cfg) as c, c.cursor() as cur:
        cur.execute(
            f"""select {_COLS}, ts_rank(c.fts, to_tsquery('simple', %(tsq)s)) as rank
                from chunks c join textbooks t on t.id=c.textbook_id
                where {_FILTER} and c.fts @@ to_tsquery('simple', %(tsq)s)
                order by rank desc limit %(k)s""",
            p,
        )
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        hay = (d.get("text") or "") + " " + (d.get("chapter") or "")
        d["sim"] = lexical_sim(terms, hay)
        d["rrf"] = float(d.pop("rank", 0.0) or 0.0)
        out.append(d)
    out.sort(key=lambda x: (-x["sim"], -x["rrf"]))
    return out


def merge_neighbor_text(chunk: dict, neighbor: dict | None, min_chars: int = 180, max_total: int = 1200) -> dict:
    """Append adjacent same-chapter chunk text when a top chunk is only a short heading or fragment."""
    if not neighbor:
        return chunk
    base = (chunk.get("text") or "").strip()
    extra = (neighbor.get("text") or "").strip()
    if len(base) >= min_chars or not extra or extra in base:
        return chunk
    combined = f"{base}\n{extra}"[:max_total]
    return {**chunk, "text": combined}


def _expand_short_chunks(chunks: list[dict], cur, min_chars: int = 180) -> list[dict]:
    out = []
    for c in chunks:
        if len((c.get("text") or "").strip()) < min_chars and c.get("book_id") and c.get("chapter_no") is not None:
            cur.execute(
                "select text from chunks where textbook_id=%s and chapter_no=%s and id > %s order by id asc limit 1",
                (c["book_id"], c["chapter_no"], c["id"]),
            )
            nbr = cur.fetchone()
            out.append(merge_neighbor_text(c, nbr, min_chars=min_chars))
        else:
            out.append(c)
    return out


def hybrid_search(
    question: str,
    class_level: int,
    subject: str | None,
    k: int = 30,
    cfg=None,
    embed_fn=None,
    *,
    curriculum_id: str = "nctb",
    textbook_medium: str = "bangla_version",
):
    from .db import get_conn

    cfg = cfg or get_config()
    norm_q = normalize_for_retrieval(question)
    if cfg.embed_provider == "fts" and embed_fn is None:
        return fts_search(
            norm_q,
            class_level,
            subject,
            k=k,
            cfg=cfg,
            curriculum_id=curriculum_id,
            textbook_medium=textbook_medium,
        )

    terms = fts_terms(norm_q)
    tsq = " | ".join(terms)
    qvec = _embed.to_pgvector((embed_fn or _embed.embed_query)(norm_q))
    p = {
        "curr": curriculum_id,
        "med": textbook_medium,
        "cl": class_level,
        "subj": subject,
        "q": norm_q,
        "tsq": tsq,
        "vec": qvec,
        "k": k,
    }
    rows: dict = {}
    vec_ids, kw_ids = [], []
    with get_conn(cfg) as c, c.cursor() as cur:
        cur.execute(
            f"""select {_COLS}, 1 - (c.embedding <=> %(vec)s::vector) as sim
                from chunks c join textbooks t on t.id=c.textbook_id
                where {_FILTER} and c.embedding is not null
                order by c.embedding <=> %(vec)s::vector limit %(k)s""",
            p,
        )
        for r in cur.fetchall():
            rows[r["id"]] = r
            vec_ids.append(r["id"])

        if tsq:
            cur.execute(
                f"""select {_COLS},
                           case when c.embedding is not null then 1 - (c.embedding <=> %(vec)s::vector) else 0.0 end as sim,
                           c.embedding is not null as has_emb
                    from chunks c join textbooks t on t.id=c.textbook_id
                    where {_FILTER} and c.fts @@ to_tsquery('simple', %(tsq)s)
                    order by ts_rank(c.fts, to_tsquery('simple', %(tsq)s)) desc limit %(k)s""",
                p,
            )
            for r in cur.fetchall():
                d = dict(r)
                has_emb = d.pop("has_emb", False)
                if not has_emb:
                    d["sim"] = lexical_sim(terms, (d.get("text") or "") + " " + (d.get("chapter") or ""))
                if d["id"] not in rows:
                    rows[d["id"]] = d
                kw_ids.append(d["id"])

        fused = rrf([vec_ids, kw_ids])
        out = []
        for cid, score in fused:
            d = dict(rows[cid])
            d["rrf"] = score
            out.append(d)
        return (_expand_short_chunks(out[:8], cur) + out[8:]) if out else out


def _rerank(question: str, chunks: list[dict], top: int) -> list[dict]:
    from sentence_transformers import CrossEncoder

    global _ce
    try:
        _ce
    except NameError:
        _ce = CrossEncoder("BAAI/bge-reranker-v2-m3")
    scores = _ce.predict([(question, c["text"]) for c in chunks])
    ranked = sorted(zip(chunks, scores), key=lambda x: -x[1])
    return [c for c, _ in ranked[:top]]


def search(
    question: str,
    class_level: int,
    subject: str | None = None,
    k: int | None = None,
    cfg=None,
    *,
    curriculum_id: str = "nctb",
    textbook_medium: str = "bangla_version",
):
    """Final top-k chunks strictly isolated to curriculum_id & textbook_medium."""
    cfg = cfg or get_config()
    k = k or cfg.rerank_k
    cands = hybrid_search(
        question,
        class_level,
        subject,
        k=cfg.retrieve_k,
        cfg=cfg,
        curriculum_id=curriculum_id,
        textbook_medium=textbook_medium,
    )
    if cfg.rerank and cands:
        return _rerank(question, cands, k)
    return cands[:k]
