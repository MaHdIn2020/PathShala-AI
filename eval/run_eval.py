"""Eval runner (stdlib only). Usage:
  python -m eval.run_eval --api http://localhost:8000 --golden eval/golden_set.jsonl --out eval/results.json [--baseline]
golden row: {id, class_level, subject, question, answerable, keywords[], gold_chapters[] (chapter_no), gold_refs[] (chunk_ref, optional)}"""
import argparse
import json
import time
import urllib.request


def keyword_recall(answer: str, keywords) -> float:
    if not keywords:
        return 0.0
    a = (answer or "").lower()
    return sum(1 for k in keywords if str(k).lower() in a) / len(keywords)


def judge_prompt(question: str, answer: str, keywords) -> str:
    kw = ", ".join(str(k) for k in (keywords or []))
    return (
        "You are an impartial Bangla primary-school grader. "
        "Decide if the student ANSWER correctly addresses the QUESTION using the expected key concepts "
        "(valid Bangla paraphrases count as PASS). Reply JSON only: {\"verdict\": \"PASS\"|\"FAIL\"}.\n\n"
        f"QUESTION: {question}\nEXPECTED CONCEPTS: {kw}\nANSWER: {answer}"
    )


def parse_judge_verdict(obj: dict) -> bool:
    return str((obj or {}).get("verdict", "")).strip().upper() == "PASS"


def score_item(item: dict, resp: dict, judge_fn=None) -> dict:
    refused = bool(resp.get("refused"))
    if item.get("answerable", True):
        correct = (not refused) and keyword_recall(resp.get("answer", ""), item.get("keywords", [])) >= 0.5
        cites = resp.get("citations", [])
        chs = {c.get("chapter_no") for c in cites}
        refs = {c.get("chunk_ref") for c in cites}
        cite_ok = (not refused) and (bool(chs & set(item.get("gold_chapters", []))) or bool(refs & set(item.get("gold_refs", []))))
        row = {"id": item.get("id"), "answerable": True, "correct": correct, "cite_ok": cite_ok, "refused": refused}
        if judge_fn is not None:
            row["judge_ok"] = (not refused) and bool(judge_fn(item, resp))
        return row
    return {"id": item.get("id"), "answerable": False, "refusal_ok": refused, "refused": refused}


def _p95(xs):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[int(0.95 * (len(xs) - 1))]


def summarize(rows, latencies, costs) -> dict:
    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]
    div = lambda a, b: (a / b) if b else None  # noqa: E731
    out = {
        "n": len(rows),
        "answer_accuracy": div(sum(r["correct"] for r in ans), len(ans)),
        "citation_correctness": div(sum(r["cite_ok"] for r in ans), len(ans)),
        "refusal_accuracy": div(sum(r["refusal_ok"] for r in unans), len(unans)),
        "p95_latency_ms": _p95(latencies),
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
        t = time.time()
        try:
            resp = _post(api, path, {"question": it["question"], "class_level": it["class_level"], "subject": it.get("subject")})
        except Exception as e:  # keep going; count as refused/incorrect
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
