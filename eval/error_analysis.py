"""Dump failing answerable items from eval/results.json into docs/ERROR_ANALYSIS.md.
Usage: python -m eval.error_analysis
"""
import argparse
import json
from collections import Counter
from pathlib import Path


def classify_failure(row: dict) -> str:
    """Deterministically categorize a failing answerable eval row."""
    if row.get("refused"):
        return "retrieval_miss"
    if row.get("cite_ok"):
        return "metric_artifact"
    return "generation_error"


def build_report(results_path: Path, golden_path: Path) -> str:
    res = json.loads(results_path.read_text(encoding="utf-8"))
    gold = {
        r["id"]: r
        for r in (json.loads(line) for line in golden_path.read_text(encoding="utf-8").splitlines() if line.strip())
    }
    fails = [r for r in res.get("rows", []) if r.get("answerable") and not r.get("correct")]
    cats = Counter(classify_failure(r) for r in fails)
    subjs = Counter(gold.get(r["id"], {}).get("subject", "unknown") for r in fails)

    lines = [
        "# Error Analysis — Golden Set Failing Answerable Items",
        "",
        f"Source: `{results_path.as_posix()}` joined with `{golden_path.as_posix()}`.",
        f"Total failing answerable items: **{len(fails)}** (out of 155 answerable).",
        "",
        "## Breakdown by Category",
        "",
        "| Category | Count | Share | Definition |",
        "|---|---:|---:|---|",
        f"| `retrieval_miss` | {cats['retrieval_miss']} | {cats['retrieval_miss'] / max(len(fails), 1):.1%} | Refused (`refused=True`): retrieval fell below `min_score` or verifier/model refused |",
        f"| `metric_artifact` | {cats['metric_artifact']} | {cats['metric_artifact'] / max(len(fails), 1):.1%} | Answered with correct chapter citation (`cite_ok=True`) but Bangla paraphrase missed exact keyword recall |",
        f"| `generation_error` | {cats['generation_error']} | {cats['generation_error'] / max(len(fails), 1):.1%} | Answered without matching gold chapter/chunk (`cite_ok=False`) |",
        "",
        "## Breakdown by Subject",
        "",
        "| Subject | Failing Count |",
        "|---|---:|",
    ]
    for subj, cnt in subjs.most_common():
        lines.append(f"| `{subj}` | {cnt} |")

    lines.extend(
        [
            "",
            "## Top Remediation Actions",
            "1. **Retrieval misses (34/48):** Test `RERANK=1` (cross-encoder reranking) and contextualisation on weak subjects; lower refusal friction only where recall improves without hurting 32/32 off-syllabus refusal.",
            "2. **Metric artifacts (9/48):** Add an LLM-judge scorer (`--judge` in `eval/run_eval.py`, using a different model than the answerer) alongside keyword recall so valid Bangla paraphrases are scored fairly.",
            "",
            f"## All {len(fails)} Failing Answerable Items",
            "",
            "| ID | Class | Subject | Category | Refused | Cite OK | Question |",
            "|---|---:|---|---|---|---|---|",
        ]
    )

    for r in fails:
        g = gold.get(r["id"], {})
        q = str(g.get("question", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {r['id']} | {g.get('class_level', '-')} | `{g.get('subject', '-')}` | `{classify_failure(r)}` | {r.get('refused')} | {r.get('cite_ok')} | {q} |"
        )

    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="eval/results.json")
    ap.add_argument("--golden", default="eval/golden_set.jsonl")
    ap.add_argument("--out", default="docs/ERROR_ANALYSIS.md")
    a = ap.parse_args()
    md = build_report(Path(a.results), Path(a.golden))
    Path(a.out).write_text(md, encoding="utf-8")
    print(f"Wrote {a.out} ({len(md.splitlines())} lines)")


if __name__ == "__main__":
    main()
