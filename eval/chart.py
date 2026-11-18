"""Render RAG vs Baseline evaluation chart (PNG via Pillow, no matplotlib needed).
Usage: python -m eval.chart [--rag eval/results.json] [--baseline eval/results_baseline.json] [--out docs/eval_chart.png]
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _pct(val) -> float:
    return max(0.0, min(1.0, float(val or 0.0)))


def render_chart(rag_summary: dict, base_summary: dict, out_path: str | Path) -> Path:
    """Draw a 900x520 PNG bar chart comparing RAG vs Baseline metrics + latency/cost table."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    w, h = 900, 520
    img = Image.new("RGB", (w, h), "#f8fafc")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    # Title
    draw.text((40, 24), "PathShala AI Evaluation: RAG vs Plain LLM Baseline", fill="#0f172a", font=font)
    draw.text((40, 44), f"Sample size n = {rag_summary.get('n', 0)}", fill="#475569", font=font)

    # Legend
    draw.rectangle([620, 26, 636, 40], fill="#059669")
    draw.text((644, 27), "RAG (PathShala AI)", fill="#0f172a", font=font)
    draw.rectangle([620, 48, 636, 62], fill="#94a3b8")
    draw.text((644, 49), "Baseline (No Retrieval)", fill="#0f172a", font=font)

    # Plot area
    left, top, right, bottom = 80, 90, 840, 350
    draw.line([(left, top), (left, bottom), (right, bottom)], fill="#cbd5e1", width=2)
    for tick in (0, 25, 50, 75, 100):
        y = int(bottom - (tick / 100.0) * (bottom - top))
        draw.line([(left, y), (right, y)], fill="#e2e8f0", width=1)
        draw.text((38, y - 6), f"{tick}%", fill="#64748b", font=font)

    metrics = [
        ("Answer Accuracy", "answer_accuracy"),
        ("Citation Correctness", "citation_correctness"),
        ("Refusal Accuracy", "refusal_accuracy"),
    ]
    group_w = (right - left) // len(metrics)
    bar_w = 64

    for idx, (label, key) in enumerate(metrics):
        cx = left + idx * group_w + group_w // 2
        rag_v = _pct(rag_summary.get(key))
        base_v = _pct(base_summary.get(key))

        # RAG bar
        rx0, rx1 = cx - bar_w - 6, cx - 6
        ry0 = int(bottom - rag_v * (bottom - top))
        draw.rectangle([rx0, ry0, rx1, bottom], fill="#059669")
        draw.text((rx0 + 12, max(top - 16, ry0 - 16)), f"{rag_v * 100:.1f}%", fill="#065f46", font=font)

        # Baseline bar
        bx0, bx1 = cx + 6, cx + bar_w + 6
        by0 = int(bottom - base_v * (bottom - top))
        draw.rectangle([bx0, by0, bx1, bottom], fill="#94a3b8")
        draw.text((bx0 + 12, max(top - 16, by0 - 16)), f"{base_v * 100:.1f}%", fill="#475569", font=font)

        draw.text((cx - len(label) * 3, bottom + 14), label, fill="#1e293b", font=font)

    # Summary table
    ty = 400
    draw.rectangle([40, ty, 860, ty + 90], fill="#ffffff", outline="#cbd5e1")
    draw.text((60, ty + 14), "Mode", fill="#475569", font=font)
    draw.text((260, ty + 14), "Answer Acc", fill="#475569", font=font)
    draw.text((400, ty + 14), "Citation Acc", fill="#475569", font=font)
    draw.text((540, ty + 14), "Refusal Acc", fill="#475569", font=font)
    draw.text((670, ty + 14), "p95 Latency", fill="#475569", font=font)
    draw.text((775, ty + 14), "Mean Cost", fill="#475569", font=font)
    draw.line([(40, ty + 34), (860, ty + 34)], fill="#e2e8f0", width=1)

    for row_i, (name, s) in enumerate((("RAG (PathShala AI)", rag_summary), ("Baseline (Plain LLM)", base_summary))):
        ry = ty + 44 + row_i * 22
        p95 = s.get("p95_latency_ms")
        cost = s.get("mean_cost_usd")
        draw.text((60, ry), name, fill="#0f172a", font=font)
        draw.text((260, ry), f"{_pct(s.get('answer_accuracy')) * 100:.1f}%", fill="#0f172a", font=font)
        draw.text((400, ry), f"{_pct(s.get('citation_correctness')) * 100:.1f}%", fill="#0f172a", font=font)
        draw.text((540, ry), f"{_pct(s.get('refusal_accuracy')) * 100:.1f}%", fill="#0f172a", font=font)
        draw.text((670, ry), f"{p95} ms" if p95 is not None else "-", fill="#0f172a", font=font)
        draw.text((775, ry), f"${cost:.5f}" if cost is not None else "-", fill="#0f172a", font=font)

    img.save(out, format="PNG")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rag", default="eval/results.json")
    ap.add_argument("--baseline", default="eval/results_baseline.json")
    ap.add_argument("--out", default="docs/eval_chart.png")
    a = ap.parse_args(argv)

    rag_p, base_p = Path(a.rag), Path(a.baseline)
    if not rag_p.exists() or not base_p.exists():
        print(f"missing results JSON ({rag_p} or {base_p}); run make eval first", file=sys.stderr)
        return 1
    rag = json.loads(rag_p.read_text(encoding="utf-8")).get("summary", {})
    base = json.loads(base_p.read_text(encoding="utf-8")).get("summary", {})
    out = render_chart(rag, base, a.out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

