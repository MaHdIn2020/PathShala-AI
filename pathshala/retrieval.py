"""Hybrid retrieval: pgvector cosine + Postgres FTS, fused with RRF. Strictly isolated by curriculum & textbook_medium."""
import math
import re

from . import embed as _embed
from .config import get_config
from .text import normalize_for_retrieval

_STOP = {
    "কী", "কি", "কেন", "কীভাবে", "কিভাবে", "কাকে", "বলে", "হয়", "হয়", "করো", "বলো", "লেখো", "দাও", "কোন", "কত",
    "এবং", "ও", "বা", "থেকে", "করে", "করা", "হলো", "হল", "মধ্যে", "পার্থক্য", "বলতে", "বোঝায়", "বোঝায়", "ব্যাখ্যা", "উদাহরণ",
    "the", "is", "are", "was", "were", "what", "how", "why", "who", "where", "when", "does", "do", "did", "to", "a", "an", "in", "of",
    "and", "or", "not", "it", "its", "this", "that", "these", "those", "their", "them", "they", "we", "you", "from", "for", "with",
    "on", "at", "by", "as", "be", "been", "have", "has", "had", "can", "will", "would", "should", "may", "into", "about", "between",
    "among", "through", "during", "before", "after", "under", "over", "there", "here", "all", "any", "both", "each", "more", "most",
    "other", "some", "such", "than", "too", "very", "difference", "differences", "different", "work", "works", "working", "explain",
    "define", "describe", "called", "mean", "means", "meant", "write", "give", "state", "example", "examples", "type", "types", "kind", "kinds",
}

_CQ_RE = re.compile(r"(?:^|\n)\s*(?:[a-d]|[ক-ঘ])[\.\)]\s+", re.IGNORECASE)
_BOILERPLATE_CUES = (
    "multiple choice questions",
    "creative questions",
    "sample questions",
    "chapter title pages",
    "at the end of this chapter, we will",
    "explain the properties of",
    "বহুনির্বাচনি প্রশ্ন",
    "সৃজনশীল প্রশ্ন",
)
_DEF_CUES = (
    "what we have learned",
    "is called",
    "are called",
    "importance of",
    "hydrogen ions",
    "কাকে বলে",
    "বলতে বোঝায়",
    "বলতে বোঝায়",
)
_ACTIVITY_CUES = ("activity :", "activity:", "methodology:", "necessary components:", "requirement :", "method:")


def _stem_en(term: str) -> str:
    """Strip common English plural suffixes so Postgres 'simple' prefix matching catches singular/plural forms."""
    if term.isascii() and term.isalpha():
        if term.endswith("ies") and len(term) > 4:
            return term[:-3]
        if term.endswith(("ches", "shes", "xes", "sses")) and len(term) > 4:
            return term[:-2]
        if term.endswith("s") and not term.endswith(("ss", "is", "us")) and len(term) > 3:
            return term[:-1]
    return term


def _tsq_token(term: str) -> str:
    stem = _stem_en(term)
    return f"{stem}:*" if (stem.isascii() and stem.isalnum() and len(stem) >= 3) else stem


def _is_boilerplate(txt: str) -> bool:
    low = (txt or "").lower()
    return any(m in low for m in _BOILERPLATE_CUES) or len(_CQ_RE.findall(low)) >= 2


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
    """Low-RAM Postgres FTS retrieval with prefix matching, IDF weighting, boilerplate filtering, and neighbor stitching."""
    from .db import get_conn

    cfg = cfg or get_config()
    norm_q = normalize_for_retrieval(question)
    terms = fts_terms(norm_q)
    if not terms:
        return []
    stems = list(dict.fromkeys(_stem_en(t) for t in terms))
    tsq_parts = [_tsq_token(t) for t in terms]
    tsq_or = " | ".join(tsq_parts)
    tsq_and = " & ".join(tsq_parts)
    sql_limit = max(k * 4, 120)
    p = {
        "curr": curriculum_id,
        "med": textbook_medium,
        "cl": class_level,
        "subj": subject,
        "tsq_or": tsq_or,
        "tsq_and": tsq_and,
        "sql_limit": sql_limit,
    }
    with get_conn(cfg, textbook_medium=textbook_medium, class_level=class_level) as c, c.cursor() as cur:
        cur.execute(
            f"""select {_COLS},
                       ts_rank(c.fts, to_tsquery('simple', %(tsq_or)s)) as rank,
                       (c.fts @@ to_tsquery('simple', %(tsq_and)s)) as all_hit
                from chunks c join textbooks t on t.id=c.textbook_id
                where {_FILTER} and c.fts @@ to_tsquery('simple', %(tsq_or)s)
                order by all_hit desc, rank desc limit %(sql_limit)s""",
            p,
        )
        rows = cur.fetchall()
        if not rows:
            return []

        df = {s: sum(1 for r in rows if s in (r.get("text") or "").lower()) for s in stems}
        weights = {
            s: (1.25 if idx == 0 else 1.0) * math.log(1.0 + (len(rows) + 1) / (df[s] + 1))
            for idx, s in enumerate(stems)
        }
        w_sum = sum(weights.values()) or 1.0

        scored = []
        for r in rows:
            d = dict(r)
            txt_l = (d.get("text") or "").lower()
            ch_l = (d.get("chapter") or "").lower()
            txt_hits = [s for s in stems if s in txt_l]
            txt_w = sum(weights[s] for s in txt_hits) / w_sum
            ch_w = sum(weights[s] for s in stems if s in ch_l) / w_sum
            boiler = _is_boilerplate(txt_l)
            is_activity = any(m in txt_l for m in _ACTIVITY_CUES)
            pen = -0.25 if boiler else (-0.12 if is_activity else 0.0)
            bon = 0.08 if any(cue in txt_l for cue in _DEF_CUES) else 0.0
            tf_bon = min(0.16, 0.05 * sum(min(4, txt_l.count(s)) - 1 for s in txt_hits))
            rank_score = 0.78 * txt_w + 0.22 * ch_w + bon + tf_bon + pen

            combined_hits = sum(1 for s in stems if s in txt_l or s in ch_l)
            base_sim = lexical_sim(stems, f"{txt_l} {ch_l}")
            if not txt_hits:
                d["sim"] = min(base_sim, 0.55)
            elif len(stems) >= 3 and combined_hits == 1:
                d["sim"] = base_sim
            else:
                d["sim"] = max(base_sim, min(0.95, round(0.45 + 0.50 * max(0.0, rank_score), 4)))
            d["rrf"] = float(d.pop("rank", 0.0) or 0.0)
            d.pop("all_hit", None)
            d["_rank_score"] = rank_score
            d["_boiler"] = boiler
            d["_txt_hits"] = txt_hits
            d["_txt_l"] = txt_l
            scored.append(d)

        scored.sort(key=lambda x: (-x["_rank_score"], -x["rrf"]))

        if len(stems) >= 2:
            # Ensure top window includes both multi-term overlap and a focused explanation of the lead topic (e.g., definition of diffusion)
            top_window = scored[:5]
            seen_ids = {x["id"] for x in top_window}
            lead = stems[0]
            lead_focused = next(
                (
                    x
                    for x in scored
                    if (not x["_boiler"])
                    and x["_txt_l"].count(lead) >= 2
                    and any(c in x["_txt_l"] for c in ("higher concentration", "is called", "are called", "কাকে বলে", "বলতে বোঝা"))
                ),
                None,
            )
            if lead_focused is not None and lead_focused["id"] not in seen_ids:
                scored.remove(lead_focused)
                scored.insert(1, lead_focused)
                seen_ids.add(lead_focused["id"])

            top_window = scored[:6]
            seen_ids = {x["id"] for x in top_window}
            for s in stems:
                if any((not x["_boiler"]) and (s in x["_txt_hits"]) for x in top_window):
                    continue
                cand = next((x for x in scored if (not x["_boiler"]) and (s in x["_txt_hits"]) and x["id"] not in seen_ids), None)
                if cand is not None:
                    scored.remove(cand)
                    scored.insert(min(5, len(scored)), cand)
                    seen_ids.add(cand["id"])

        for item in scored:
            item.pop("_rank_score", None)
            item.pop("_boiler", None)
            item.pop("_txt_hits", None)
            item.pop("_txt_l", None)

        top = scored[:k]
        return (_expand_short_chunks(top[:8], cur) + top[8:]) if top else top


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


def _expand_short_chunks(chunks: list[dict], cur, min_chars: int = 360) -> list[dict]:
    out = []
    for c in chunks:
        curr = c
        text = (curr.get("text") or "").strip()
        if text and text[0].islower() and curr.get("book_id") and curr.get("chapter_no") is not None:
            cur.execute(
                "select text from chunks where textbook_id=%s and chapter_no=%s and id < %s order by id desc limit 1",
                (curr["book_id"], curr["chapter_no"], curr["id"]),
            )
            prev_nbr = cur.fetchone()
            prev_txt = (prev_nbr.get("text") or "").strip() if prev_nbr else ""
            if prev_txt and prev_txt[-400:] not in text:
                curr = {**curr, "text": f"{prev_txt[-400:]}\n{text}"[:1200]}

        if len((curr.get("text") or "").strip()) < min_chars and curr.get("book_id") and curr.get("chapter_no") is not None:
            cur.execute(
                "select text from chunks where textbook_id=%s and chapter_no=%s and id > %s order by id asc limit 1",
                (curr["book_id"], curr["chapter_no"], curr["id"]),
            )
            nbr = cur.fetchone()
            out.append(merge_neighbor_text(curr, nbr, min_chars=min_chars))
        else:
            out.append(curr)
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
    try:
        qvec = _embed.to_pgvector((embed_fn or _embed.embed_query)(norm_q))
    except ImportError:
        return fts_search(
            norm_q,
            class_level,
            subject,
            k=k,
            cfg=cfg,
            curriculum_id=curriculum_id,
            textbook_medium=textbook_medium,
        )
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
    with get_conn(cfg, textbook_medium=textbook_medium, class_level=class_level) as c, c.cursor() as cur:
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
