"""Calibrate MIN_SCORE on 30 in-syllabus + 30 off-syllabus questions and check recall@5 on 15 questions.
Usage: python scripts/calibrate_min_score.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

THRESHOLDS = [round(0.25 + 0.05 * i, 2) for i in range(8)]  # 0.25 .. 0.60


def sweep_thresholds(in_scores: list[float], off_scores: list[float], thresholds: list[float] | None = None) -> list[dict]:
    """Evaluate candidate MIN_SCORE thresholds over top similarity scores."""
    thresholds = thresholds or THRESHOLDS
    total = len(in_scores) + len(off_scores)
    rows = []
    for t in thresholds:
        in_ok = sum(1 for s in in_scores if s >= t)
        off_ok = sum(1 for s in off_scores if s < t)
        rows.append(
            {
                "threshold": t,
                "answer_rate": round(in_ok / len(in_scores), 4) if in_scores else 0.0,
                "refusal_acc": round(off_ok / len(off_scores), 4) if off_scores else 0.0,
                "overall_acc": round((in_ok + off_ok) / total, 4) if total else 0.0,
            }
        )
    return rows


def pick_threshold(rows: list[dict], min_answer_rate: float = 0.90) -> dict:
    """Pick threshold maximizing refusal_acc while keeping answer_rate >= min_answer_rate."""
    eligible = [r for r in rows if r["answer_rate"] >= min_answer_rate]
    pool = eligible if eligible else rows
    return max(pool, key=lambda r: (r["refusal_acc"], r["overall_acc"], -r["threshold"]))


def main(golden_path: str = "eval/golden_set.jsonl") -> int:
    from pathshala.retrieval import search

    items = [json.loads(line) for line in Path(golden_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    # Hold out every 5th row (20% TEST) and calibrate only on the 80% dev split
    dev = [it for i, it in enumerate(items) if i % 5 != 0]
    in_dev = [it for it in dev if it.get("answerable")][:30]
    off_all = [it for it in items if not it.get("answerable")][:30]

    in_scores, off_scores = [], []
    recall_hits = 0
    print("--- T10: Recall@5 check on 15 dev answerable questions ---")
    for idx, it in enumerate(in_dev):
        chunks = search(it["question"], it["class_level"], it.get("subject"), k=5)
        top = max((c.get("sim", 0.0) for c in chunks), default=0.0)
        in_scores.append(top)
        if idx < 15:
            chs = {c.get("chapter_no") for c in chunks}
            refs = {c.get("chunk_ref") for c in chunks}
            hit = bool(chs & set(it.get("gold_chapters", []))) or bool(refs & set(it.get("gold_refs", [])))
            recall_hits += int(hit)
            print(f"  {idx + 1:2d}. [{it['id']}] sim={top:.3f} hit={hit} gold_ch={it.get('gold_chapters')} got_ch={[c.get('chapter_no') for c in chunks[:3]]}")

    print(f"Recall@5 (15 questions): {recall_hits}/15 ({recall_hits / 15 * 100:.1f}%)")

    for it in off_all:
        chunks = search(it["question"], it["class_level"], it.get("subject"), k=5)
        top = max((c.get("sim", 0.0) for c in chunks), default=0.0)
        off_scores.append(top)

    in_s, off_s = sorted(in_scores), sorted(off_scores)
    print(f"\nin_scores  (n={len(in_s)}): min={in_s[0]:.3f} median={in_s[len(in_s)//2]:.3f} max={in_s[-1]:.3f}")
    print(f"off_scores (n={len(off_s)}): min={off_s[0]:.3f} median={off_s[len(off_s)//2]:.3f} max={off_s[-1]:.3f}")

    table = sweep_thresholds(in_scores, off_scores)
    print("\n--- T09: MIN_SCORE sweep (60 questions) ---")
    for r in table:
        print(f"  t={r['threshold']:.2f}  answer_rate={r['answer_rate']*100:5.1f}%  refusal_acc={r['refusal_acc']*100:5.1f}%  overall={r['overall_acc']*100:5.1f}%")
    best = pick_threshold(table)
    print(f"Recommended MIN_SCORE={best['threshold']:.2f} -> {best}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

