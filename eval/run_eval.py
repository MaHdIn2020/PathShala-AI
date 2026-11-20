"""Eval runner (stdlib only). Usage:
  python -m eval.run_eval --api http://localhost:8000 --golden eval/golden_set.jsonl --out eval/results.json [--baseline]
Supports v1 and v2 golden rows with curriculum_id, textbook_medium, and answer_language."""
import argparse
import json
import math
import random
import time
import urllib.request


def split_dev_test(items: list[dict], test_ratio: float = 0.2, seed: int = 42) -> tuple[list[dict], list[dict]]:
    """Deterministic dev/test split with fixed seed."""
    idxs = list(range(len(items)))
    rng = random.Random(seed)
    rng.shuffle(idxs)
    n_test = max(1, int(round(len(items) * test_ratio))) if items else 0
    test_set = set(idxs[:n_test])
    dev = [it for i, it in enumerate(items) if i not in test_set]
    test = [it for i, it in enumerate(items) if i in test_set]
    return dev, test


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score confidence interval for proportion k/n."""
    if n <= 0:
        return None
    p = k / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    half = (z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * n)) / n)) / denom
    return (round(max(0.0, center - half), 4), round(min(1.0, center + half), 4))


def keyword_recall(answer: str, keywords) -> float:
    if not keywords:
        return 0.0
    a = (answer or "").lower()
    return sum(1 for k in keywords if str(k).lower() in a) / len(keywords)


def judge_prompt(question: str, answer: str, keywords) -> str:
    kw = ", ".join(str(k) for k in (keywords or []))
    return (
        "You are an impartial Bangla primary-school grader. "
        "Grade the student ANSWER against the QUESTION and EXPECTED CONCEPTS "
        "(valid Bangla paraphrases count as correct). "
        'Reply JSON only: {"verdict": "correct"|"partially"|"wrong", "cites_right_chunk": true|false}.\n\n'
        f"QUESTION: {question}\nEXPECTED CONCEPTS: {kw}\nANSWER: {answer}"
    )


def parse_judge_verdict(obj: dict) -> bool:
    v = str((obj or {}).get("verdict", "")).strip().upper()
    return v in ("PASS", "CORRECT")


def has_version_leakage(item: dict, resp: dict) -> bool:
    """True when any returned citation comes from a mismatched textbook_medium or class_level."""
    if resp.get("refused"):
        return False
    exp_med = item.get("textbook_medium")
    exp_cls = item.get("class_level")
    for c in resp.get("citations") or []:
        c_med = c.get("textbook_medium")
        c_cls = c.get("class_level")
        if exp_med and c_med and c_med != exp_med:
            return True
        if exp_cls is not None and c_cls is not None and int(c_cls) != int(exp_cls):
            return True
    return False


def score_item(item: dict, resp: dict, judge_fn=None) -> dict:
    refused = bool(resp.get("refused"))
    err = bool(resp.get("error"))
    leak = has_version_leakage(item, resp)
    if item.get("answerable", True):
        correct = (not refused) and keyword_recall(resp.get("answer", ""), item.get("keywords", [])) >= 0.5
        cites = resp.get("citations", [])
        chs = {c.get("chapter_no") for c in cites}
        refs = {c.get("chunk_ref") for c in cites}
        cite_ok = (not refused) and (bool(chs & set(item.get("gold_chapters", []))) or bool(refs & set(item.get("gold_refs", []))))
        row = {
            "id": item.get("id"),
            "answerable": True,
            "correct": correct,
            "cite_ok": cite_ok,
            "refused": refused,
            "false_refusal": refused,
            "version_leak": leak,
            "error": err,
        }
        if judge_fn is not None:
            row["judge_ok"] = (not refused) and bool(judge_fn(item, resp))
        return row
    return {
        "id": item.get("id"),
        "answerable": False,
        "refusal_ok": refused,
        "refused": refused,
        "version_leak": leak,
        "error": err,
    }


def _pct(xs, p: float):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[int(p * (len(xs) - 1))]


def summarize(rows, latencies, costs) -> dict:
    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]
    div = lambda a, b: (a / b) if b else None  # noqa: E731
    tp_ref = sum(1 for r in unans if r.get("refusal_ok"))
    fp_ref = sum(1 for r in ans if r.get("refused"))
    out = {
        "n": len(rows),
        "answer_accuracy": div(sum(r["correct"] for r in ans), len(ans)),
        "citation_correctness": div(sum(r["cite_ok"] for r in ans), len(ans)),
        "answerable_false_refusal_rate": div(fp_ref, len(ans)),
        "refusal_accuracy": div(tp_ref, len(unans)),
        "refusal_precision": div(tp_ref, tp_ref + fp_ref) if (tp_ref + fp_ref) else None,
        "curriculum_version_leakage_count": sum(1 for r in rows if r.get("version_leak")),
        "error_rate": div(sum(1 for r in rows if r.get("error")), len(rows)),
        "p50_latency_ms": _pct(latencies, 0.50),
        "p95_latency_ms": _pct(latencies, 0.95),
        "mean_cost_usd": div(sum(costs), len(costs)),
    }
    judged = [r for r in ans if "judge_ok" in r]
    if judged:
        out["llm_judge_accuracy"] = div(sum(r["judge_ok"] for r in judged), len(judged))
    return out


def _post(api: str, path: str, body: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        api + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def run(api: str, golden: str, baseline: bool, judge_model: str | None = None) -> dict:
    items = [json.loads(line) for line in open(golden, encoding="utf-8") if line.strip()]
    path = "/baseline" if baseline else "/ask"
    judge_fn = None
    if judge_model:
        from pathshala import llm

        def _judge(it, resp):
            try:
                obj, _ = llm.chat_json(
                    "Return JSON only: {\"verdict\": \"PASS\"|\"FAIL\"}.",
                    judge_prompt(it["question"], resp.get("answer", ""), it.get("keywords", [])),
                    judge_model,
                    100,
                )
                return parse_judge_verdict(obj)
            except Exception:
                return False

        judge_fn = _judge

    rows, lat, cost = [], [], []
    for it in items:
        body = {
            "question": it["question"],
            "class_level": it["class_level"],
            "subject": it.get("subject"),
        }
        if not baseline:
            body["curriculum_id"] = it.get("curriculum_id", "nctb")
            body["textbook_medium"] = it.get("textbook_medium", "bangla_version")
            body["answer_language"] = it.get("answer_language", "bn")
        t = time.time()
        try:
            resp = _post(api, path, body)
        except Exception as e:
            resp = {"refused": True, "answer": "", "citations": [], "error": str(e)}
        lat.append(int((time.time() - t) * 1000))
        cost.append(float(resp.get("cost_usd") or 0.0))
        rows.append(score_item(it, resp, judge_fn=judge_fn))
    return {"mode": "baseline" if baseline else "rag", "summary": summarize(rows, lat, cost), "rows": rows}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--golden", default="eval/golden_set.jsonl")
    ap.add_argument("--out", default="eval/results.json")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--judge", default=None, help="Optional judge model (different from answerer)")
    a = ap.parse_args()
    res = run(a.api, a.golden, a.baseline, judge_model=a.judge)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=2))
