"""K-means clustering of anonymous student questions for teacher topic discovery."""
from collections import Counter

from .config import get_config
from .text import normalize_bangla


def cluster_records(records: list[dict], k: int = 6, llm_fn=None, model: str | None = None) -> list[dict]:
    """Group query dicts into <=8 k-means clusters over char n-gram TF-IDF features."""
    clean = [r for r in records if normalize_bangla(r.get("question") or "")]
    if not clean:
        return []

    texts = [normalize_bangla(r["question"]) for r in clean]
    n_clusters = max(1, min(k, 8, len(set(texts))))

    if n_clusters == 1:
        labels = [0] * len(clean)
    else:
        from sklearn.cluster import KMeans
        from sklearn.feature_extraction.text import TfidfVectorizer

        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
        mat = vec.fit_transform(texts)
        labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(mat).tolist()

    groups: dict[int, list[dict]] = {}
    for row, cid in zip(clean, labels):
        groups.setdefault(int(cid), []).append(row)

    out = []
    for cid, rows in groups.items():
        size = len(rows)
        refused = sum(1 for r in rows if r.get("refused"))
        topic_counts = Counter(r.get("topic") for r in rows if r.get("topic"))
        top_topic = topic_counts.most_common(1)[0][0] if topic_counts else None
        q_counts = Counter(normalize_bangla(r["question"]) for r in rows)
        samples = [q for q, _ in q_counts.most_common(3)]
        label = top_topic or samples[0][:40]

        if llm_fn and model:
            try:
                sys_p = "Give a short 2-5 word Bangla topic label for these student questions. Output label only."
                user_p = "\n".join(f"- {s}" for s in samples)
                txt, _ = llm_fn(sys_p, user_p, model, 40)
                if txt and txt.strip():
                    label = txt.strip()[:60]
            except Exception:
                pass

        out.append(
            {
                "cluster_id": cid,
                "label": label,
                "size": size,
                "refused": refused,
                "refusal_rate": round(refused / size, 4) if size > 0 else 0.0,
                "top_topic": top_topic,
                "sample_questions": samples,
            }
        )

    out.sort(key=lambda c: (-c["size"], c["cluster_id"]))
    return out


def cluster_db_queries(k: int = 6, use_llm: bool = False, limit: int = 500) -> list[dict]:
    from . import db, llm

    cfg = get_config()
    with db.get_conn(cfg) as c, c.cursor() as cur:
        cur.execute(
            "select question, topic, class_level, subject, refused from queries where question is not null order by id desc limit %s",
            (limit,),
        )
        rows = cur.fetchall()
    return cluster_records(rows, k=k, llm_fn=llm.chat_text if use_llm else None, model=cfg.llm_fast_model)

