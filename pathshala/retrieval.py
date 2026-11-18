"""Hybrid retrieval: pgvector cosine + Postgres FTS, fused with RRF. Optional cross-encoder rerank."""
from .config import get_config
from . import embed as _embed


def rrf(rank_lists, k: int = 60, top: int | None = None):
    """Reciprocal Rank Fusion. rank_lists: list of ordered id lists. Returns [(id, score)] best first."""
    scores: dict = {}
    for lst in rank_lists:
        for r, i in enumerate(lst):
            scores[i] = scores.get(i, 0.0) + 1.0 / (k + r + 1)
    out = sorted(scores.items(), key=lambda x: (-x[1], str(x[0])))
    return out[:top] if top else out


_COLS = "c.id, c.chunk_ref, c.text, c.contextual_text, c.chapter_no, c.chapter, c.page_start, c.page_end, t.title as book, t.id as book_id, t.class_level, t.subject"
_FILTER = "t.class_level = %(cl)s and (%(subj)s::text is null or t.subject = %(subj)s)"


def hybrid_search(question: str, class_level: int, subject: str | None, k: int = 30, cfg=None, embed_fn=None):
    from .db import get_conn

    cfg = cfg or get_config()
    qvec = _embed.to_pgvector((embed_fn or _embed.embed_query)(question))
    p = {"cl": class_level, "subj": subject, "q": question, "vec": qvec, "k": k}
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
        cur.execute(
            f"""select {_COLS}, 0.0::float as sim
                from chunks c join textbooks t on t.id=c.textbook_id
                where {_FILTER} and c.fts @@ plainto_tsquery('simple', %(q)s)
                order by ts_rank(c.fts, plainto_tsquery('simple', %(q)s)) desc limit %(k)s""",
            p,
        )
        for r in cur.fetchall():
            if r["id"] not in rows:
                rows[r["id"]] = r
            kw_ids.append(r["id"])
    fused = rrf([vec_ids, kw_ids])
    out = []
    for cid, score in fused:
        d = dict(rows[cid])
        d["rrf"] = score
        out.append(d)
    return out


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


def search(question: str, class_level: int, subject: str | None = None, k: int | None = None, cfg=None):
    """Final top-k chunks (hybrid + optional rerank). Each chunk has 'sim' (cosine) for refusal gating."""
    cfg = cfg or get_config()
    k = k or cfg.rerank_k
    cands = hybrid_search(question, class_level, subject, k=cfg.retrieve_k, cfg=cfg)
    if cfg.rerank and cands:
        return _rerank(question, cands, k)
    return cands[:k]
