"""Pure prep step between load and embed: normalise, drop empty, dedupe, split oversize, filter classes."""
from collections import Counter

from pathshala.text import _split_long, normalize_bangla

MAX_CHARS = 1500


def _suffix(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(97 + r) + s
    return s


def prepare(recs: list[dict], max_class: int = 5, max_chars: int = MAX_CHARS) -> tuple[list[dict], dict]:
    """Returns (clean records, stats). Oversize chunks are split; refs get suffix -a, -b ..."""
    stats = Counter()
    out, seen = [], set()
    for r in recs:
        if max_class and r["class_level"] > max_class:
            stats["skipped_class"] += 1
            continue
        text = normalize_bangla(r["text"])
        if not text:
            stats["dropped_empty"] += 1
            continue
        parts = _split_long(text, max_chars)
        if len(parts) > 1:
            stats["split_chunks"] += 1
        for i, p in enumerate(parts):
            ref = r["chunk_ref"] if len(parts) == 1 else f"{r['chunk_ref']}-{_suffix(i)}"
            if ref in seen:
                stats["dropped_duplicate_ref"] += 1
                continue
            seen.add(ref)
            out.append({**r, "text": p, "chunk_ref": ref})
    stats["kept"] = len(out)
    return out, dict(stats)
