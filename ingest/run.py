"""Ingest NCTB-PrimaryText -> Postgres.  python -m ingest.run --data data/raw/mendeley [--limit 50] [--no-ctx] [--dry-run]
Steps: load -> (contextualise via fast LLM, cached) -> embed (local bge-m3) -> upsert. Re-runnable (upsert on chunk_ref)."""
import argparse
import hashlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pathshala.config import get_config
from pathshala.pipeline import load_prompt

from .mendeley import load_dir
from .prepare import prepare

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "ctx"
SOURCE = "NCTB-PrimaryText (Mendeley Data, DOI 10.17632/w3hj4m45d9.1, CC BY 4.0)"


def _neighbors(recs: list[dict]) -> dict:
    """chunk_ref -> section text (chapter chunks around it, capped) for contextualisation."""
    by_ch: dict = {}
    for r in recs:
        by_ch.setdefault((r["class_level"], r["subject"], r["chapter_no"]), []).append(r)
    sec = {}
    for rows in by_ch.values():
        for i, r in enumerate(rows):
            around = rows[max(0, i - 1) : i + 2]
            sec[r["chunk_ref"]] = "\n\n".join(x["text"] for x in around)[:1500]
    return sec


def contextualise(recs: list[dict], cfg, workers: int = 4) -> float:
    from pathshala import llm

    CACHE.mkdir(parents=True, exist_ok=True)
    sec = _neighbors(recs)
    system = load_prompt("contextualizer")
    cost = [0.0]

    def one(r):
        key = hashlib.sha256(f"{r['chunk_ref']}|{r['text']}".encode()).hexdigest()
        f = CACHE / f"{key}.txt"
        if f.exists():
            r["contextual_text"] = f.read_text(encoding="utf-8")
            return
        user = (
            f"Class {r['class_level']}, subject {r['subject']}, chapter {r['chapter_no']}: {r['chapter']}\n\n"
            f"SECTION:\n{sec[r['chunk_ref']]}\n\nCHUNK:\n{r['text'][:1500]}"
        )
        try:
            txt, u = llm.chat_text(system, user, cfg.llm_fast_model, 200)
            cost[0] += u.get("cost", 0.0)
        except Exception as e:  # keep going; chunk still searchable without context
            print("ctx fail", r["chunk_ref"], str(e)[:80], file=sys.stderr)
            txt = ""
        r["contextual_text"] = txt
        if txt:
            f.write_text(txt, encoding="utf-8")

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, recs))
    return cost[0]


def embed_all(recs: list[dict], batch: int = 16) -> None:
    from pathshala.embed import embed_texts, to_pgvector

    for i in range(0, len(recs), batch):
        part = recs[i : i + batch]
        vecs = embed_texts([(r.get("contextual_text") or "") + "\n" + r["text"] for r in part])
        for r, v in zip(part, vecs):
            r["embedding"] = to_pgvector(v)
        print(f"embedded {min(i + batch, len(recs))}/{len(recs)}", end="\r")
    print()


def upsert(recs: list[dict]) -> None:
    from pathshala.db import get_conn

    with get_conn() as c, c.cursor() as cur:
        book_ids: dict = {}
        for r in recs:
            k = (r["class_level"], r["subject"])
            if k not in book_ids:
                cur.execute(
                    """insert into textbooks(title, class_level, subject, source, parser_version)
                       values (%s,%s,%s,%s,%s)
                       on conflict (class_level, subject) do update set source=excluded.source
                       returning id""",
                    (f"NCTB শ্রেণি {k[0]} · {k[1]}", k[0], k[1], SOURCE, "mendeley-v1"),
                )
                book_ids[k] = cur.fetchone()["id"]
            cur.execute(
                """insert into chunks(textbook_id, chunk_ref, chapter_no, chapter, text, contextual_text, embedding, tokens)
                   values (%s,%s,%s,%s,%s,%s,%s::vector,%s)
                   on conflict (chunk_ref) do update set text=excluded.text, chapter=excluded.chapter,
                     chapter_no=excluded.chapter_no, contextual_text=excluded.contextual_text, embedding=excluded.embedding""",
                (
                    book_ids[k],
                    r["chunk_ref"],
                    r["chapter_no"],
                    r["chapter"],
                    r["text"],
                    r.get("contextual_text") or None,
                    r["embedding"],
                    len(r["text"]) // 3,
                ),
            )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/mendeley")
    ap.add_argument("--limit", type=int, default=0, help="first N records (smoke runs)")
    ap.add_argument("--no-ctx", action="store_true", help="skip LLM contextualisation (saves quota)")
    ap.add_argument("--dry-run", action="store_true", help="load + normalise only, print stats")
    ap.add_argument("--max-class", type=int, default=5, help="highest class to ingest (0 = all classes)")
    a = ap.parse_args(argv)
    cfg = get_config()
    t0 = time.time()
    loaded = load_dir(a.data)
    recs, stats = prepare(loaded, max_class=a.max_class)
    if a.limit:
        recs = recs[: a.limit]
    print(f"loaded {len(loaded)} chunks from {a.data}; kept {len(recs)}; {stats}")
    if not recs:
        print("nothing to ingest: run scripts/inspect_dataset.py", file=sys.stderr)
        return 1
    if a.dry_run:
        refs = [r["chunk_ref"] for r in recs]
        lens = sorted(len(r["text"]) for r in recs)
        print(f"unique refs: {len(set(refs)) == len(refs)}; empty text: {sum(1 for x in lens if x == 0)}")
        print(f"chars min/median/max: {lens[0]}/{lens[len(lens) // 2]}/{lens[-1]}")
        return 0
    if not a.no_ctx:
        print(f"contextualised; llm cost ~${contextualise(recs, cfg):.4f}")
    embed_all(recs)
    upsert(recs)
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
