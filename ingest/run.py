"""Ingest NCTB datasets -> 3-shard Postgres.
Usage:
  python -m ingest.run --data data/raw/NCTB-SchoolText-English --medium english_version --max-class 0 --no-ctx
Steps: load -> prepare -> (optional ctx) -> (optional embed via bge-m3 on GPU/CPU) -> shard-routed batched upsert."""
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
SOURCE_BN = "NCTB-PrimaryText / SchoolText Bangla (Mendeley Data, DOI 10.17632/w3hj4m45d9.1, CC BY 4.0)"
SOURCE_EN = "NCTB-SchoolText English Version (CC BY 4.0)"


def _neighbors(recs: list[dict]) -> dict:
    """chunk_ref -> section text (chapter chunks around it, capped) for contextualisation."""
    by_ch: dict = {}
    for r in recs:
        by_ch.setdefault((r.get("textbook_medium"), r["class_level"], r["subject"], r["chapter_no"]), []).append(r)
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
        except Exception as e:
            print("ctx fail", r["chunk_ref"], str(e)[:80], file=sys.stderr)
            txt = ""
        r["contextual_text"] = txt
        if txt:
            f.write_text(txt, encoding="utf-8")

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, recs))
    return cost[0]


def embed_all(recs: list[dict], batch: int = 256) -> None:
    from pathshala.embed import embed_texts, to_pgvector

    for i in range(0, len(recs), batch):
        part = recs[i : i + batch]
        vecs = embed_texts([(r.get("contextual_text") or "") + "\n" + r["text"] for r in part])
        for r, v in zip(part, vecs):
            r["embedding"] = to_pgvector(v)
        print(f"embedded {min(i + batch, len(recs))}/{len(recs)}", end="\r")
    print()


def _book_title(curr: str, med: str, cls: int, subj: str) -> str:
    if med == "english_version":
        return f"NCTB Class {cls} · {subj} (English Version)"
    return f"NCTB শ্রেণি {cls} · {subj}"


def upsert(recs: list[dict], source_label: str | None = None, cfg=None) -> None:
    from pathshala.db import get_conn, resolve_db_url

    cfg = cfg or get_config()
    by_shard: dict[str, list[dict]] = {}
    for r in recs:
        url = resolve_db_url(r.get("textbook_medium"), r["class_level"], cfg)
        by_shard.setdefault(url, []).append(r)

    for shard_url, shard_recs in by_shard.items():
        with get_conn(cfg, db_url=shard_url) as c, c.cursor() as cur:
            book_ids: dict = {}
            for r in shard_recs:
                curr = r.get("curriculum_id") or "nctb"
                med = r.get("textbook_medium") or "unknown"
                k = (curr, med, r["class_level"], r["subject"])
                if k not in book_ids:
                    src = source_label or (SOURCE_EN if med == "english_version" else SOURCE_BN)
                    cur.execute(
                        """insert into textbooks(title, curriculum_id, textbook_medium, edition_year, class_level, subject, source, source_license, parser_version)
                           values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           on conflict (curriculum_id, textbook_medium, class_level, subject) do update set
                             title=excluded.title, source=excluded.source, source_license=excluded.source_license, parser_version=excluded.parser_version
                           returning id""",
                        (_book_title(*k), curr, med, r.get("edition_year") or 2024, k[2], k[3], src, "CC BY 4.0", "mendeley-v2"),
                    )
                    book_ids[k] = cur.fetchone()["id"]

            rows = [
                (
                    book_ids[(r.get("curriculum_id") or "nctb", r.get("textbook_medium") or "unknown", r["class_level"], r["subject"])],
                    r["chunk_ref"],
                    r["chapter_no"],
                    r["chapter"],
                    r.get("page_start"),
                    r.get("page_end"),
                    r["text"],
                    r.get("contextual_text") or None,
                    r.get("embedding"),
                    max(1, len(r["text"]) // 3),
                )
                for r in shard_recs
            ]
            cur.executemany(
                """insert into chunks(textbook_id, chunk_ref, chapter_no, chapter, page_start, page_end, text, contextual_text, embedding, tokens)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,%s)
                   on conflict (chunk_ref) do update set
                     textbook_id=excluded.textbook_id,
                     text=excluded.text,
                     chapter=excluded.chapter,
                     chapter_no=excluded.chapter_no,
                     page_start=coalesce(excluded.page_start, chunks.page_start),
                     page_end=coalesce(excluded.page_end, chunks.page_end),
                     contextual_text=coalesce(excluded.contextual_text, chunks.contextual_text),
                     embedding=coalesce(excluded.embedding, chunks.embedding)""",
                rows,
            )


def existing_refs(
    require_embedding: bool = True,
    *,
    medium: str | None = None,
    class_levels: set[int] | None = None,
    cfg=None,
) -> set:
    from pathshala.db import all_shard_urls, get_conn, resolve_db_url

    cfg = cfg or get_config()
    if medium and medium != "auto":
        cls_set = class_levels or ({1} if medium == "english_version" else {1, 9})
        urls = []
        for cl in sorted(cls_set):
            u = resolve_db_url(medium, cl, cfg)
            if u not in urls:
                urls.append(u)
    else:
        urls = all_shard_urls(cfg)

    sql = "select chunk_ref from chunks where embedding is not null" if require_embedding else "select chunk_ref from chunks"
    done = set()
    for url in urls:
        with get_conn(cfg, db_url=url) as c, c.cursor() as cur:
            cur.execute(sql)
            done.update(r["chunk_ref"] for r in cur.fetchall())
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/mendeley")
    ap.add_argument("--medium", default="auto", choices=("auto", "bangla_version", "english_version", "unknown"))
    ap.add_argument("--curriculum", default="nctb")
    ap.add_argument("--limit", type=int, default=0, help="first N records (smoke runs)")
    ap.add_argument("--no-ctx", action="store_true", help="skip LLM contextualisation (saves quota)")
    ap.add_argument("--fts-only", action="store_true", help="skip local bge-m3 embeddings (upsert text + FTS + page ranges)")
    ap.add_argument("--dry-run", action="store_true", help="load + normalise only, print stats")
    ap.add_argument("--max-class", type=int, default=5, help="highest class to ingest (0 = all classes)")
    ap.add_argument("--classes", default="", help="optional comma-separated class filter e.g. 1,2,8")
    ap.add_argument("--subjects", default="", help="optional comma-separated subject filter e.g. science,math")
    ap.add_argument("--save-every", type=int, default=500, help="save batch size")
    ap.add_argument("--force", action="store_true", help="re-process chunks already in DB")
    a = ap.parse_args(argv)
    cfg = get_config()
    t0 = time.time()

    loaded = load_dir(a.data, medium=a.medium, curriculum_id=a.curriculum)
    recs, stats = prepare(loaded, max_class=a.max_class)
    if a.classes.strip():
        cls_set = {int(x.strip()) for x in a.classes.split(",") if x.strip()}
        recs = [r for r in recs if r["class_level"] in cls_set]
    if a.subjects.strip():
        subj_set = {x.strip().lower() for x in a.subjects.split(",") if x.strip()}
        recs = [r for r in recs if r["subject"].lower() in subj_set]
    if a.limit:
        recs = recs[: a.limit]

    print(f"loaded {len(loaded)} chunks from {a.data}; kept {len(recs)}; {stats}")
    if not recs:
        print("nothing to ingest", file=sys.stderr)
        return 1
    if a.dry_run:
        refs = [r["chunk_ref"] for r in recs]
        lens = sorted(len(r["text"]) for r in recs)
        paged = sum(1 for r in recs if r.get("page_start") is not None)
        print(f"unique refs: {len(set(refs)) == len(refs)}; with page ranges: {paged}/{len(recs)}; empty text: {sum(1 for x in lens if x == 0)}")
        print(f"chars min/median/max: {lens[0]}/{lens[len(lens) // 2]}/{lens[-1]}")
        return 0
    if not a.no_ctx:
        print(f"contextualised; llm cost ~${contextualise(recs, cfg):.4f}")
    if not a.force:
        meds = {r.get("textbook_medium") for r in recs}
        med_arg = next(iter(meds)) if len(meds) == 1 else a.medium
        cls_arg = {r["class_level"] for r in recs}
        done = existing_refs(require_embedding=not a.fts_only, medium=med_arg, class_levels=cls_arg, cfg=cfg)
        recs = [r for r in recs if r["chunk_ref"] not in done]
        print(f"{len(done)} already in DB; {len(recs)} to do")
    for i in range(0, len(recs), a.save_every):
        part = recs[i : i + a.save_every]
        if not a.fts_only:
            embed_all(part)
        upsert(part, cfg=cfg)
        print(f"saved {min(i + a.save_every, len(recs))}/{len(recs)}  elapsed {time.time() - t0:.0f}s", flush=True)
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
