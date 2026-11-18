"""Loader for NCTB-PrimaryText (Mendeley Data, DOI 10.17632/w3hj4m45d9.1, CC BY 4.0).
Documented record fields: class, subject, chapter_no, chapter_title, chunk_id, text.
This loader is schema-tolerant: reads .jsonl, and .json (list | {chunks|data|records|items: [...]} | chapters-with-chunks).
Pure stdlib; unit-tested. Run `python scripts/inspect_dataset.py data/raw/mendeley` first to see the real shape."""
import json
import re
from pathlib import Path

_BN = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
ALIASES = {
    "class": ("class", "grade", "class_level", "class_no", "শ্রেণি"),
    "subject": ("subject", "subject_name", "book", "বিষয়"),
    "chapter_no": ("chapter_no", "chapter_number", "chapter_id", "chapter_num", "অধ্যায়_নং"),
    "chapter_title": ("chapter_title", "chapter_name", "chapter", "title", "অধ্যায়"),
    "chunk_id": ("chunk_id", "id", "chunk_ref"),
    "text": ("text", "content", "chunk", "chunk_text"),
}
_LISTY = ("chunks", "data", "records", "items", "rows")


def _first(raw: dict, key: str):
    for k in ALIASES[key]:
        if k in raw and raw[k] not in (None, ""):
            return raw[k]
    return None


def to_int(v):
    """'Class 3' | '৩' | 3 | '3rd' -> 3 ; None if no digit."""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    m = re.search(r"\d+", str(v).translate(_BN))
    return int(m.group()) if m else None


def slug_subject(v) -> str:
    s = str(v or "unknown").strip()
    return re.sub(r"\s+", "_", s).lower()


def normalize_record(raw: dict, defaults: dict | None = None) -> dict | None:
    """Return {class_level, subject, chapter_no, chapter, chunk_ref, text} or None if unusable."""
    d = {**(defaults or {})}
    text = _first(raw, "text")
    if not isinstance(text, str) or not text.strip():
        return None
    cls = to_int(_first(raw, "class")) or to_int(d.get("class"))
    subj = _first(raw, "subject") or d.get("subject")
    if cls is None or not subj:
        return None
    ch_no = to_int(_first(raw, "chapter_no"))
    if ch_no is None:
        ch_no = to_int(d.get("chapter_no"))
    title = _first(raw, "chapter_title") or d.get("chapter_title")
    ref = _first(raw, "chunk_id")
    return {
        "class_level": cls,
        "subject": slug_subject(subj),
        "chapter_no": ch_no,
        "chapter": str(title).strip() if title is not None else None,
        "chunk_ref": str(ref) if ref is not None else None,
        "text": text.strip(),
    }


def _walk(obj, defaults):
    """Yield (raw_dict, defaults) from nested JSON."""
    if isinstance(obj, list):
        for x in obj:
            if isinstance(x, dict):
                yield from _walk(x, defaults)
    elif isinstance(obj, dict):
        if _first(obj, "text") is not None and not any(isinstance(obj.get(k), list) for k in _LISTY):
            yield obj, defaults
            return
        inherit = {
            "class": _first(obj, "class") or defaults.get("class"),
            "subject": _first(obj, "subject") or defaults.get("subject"),
            "chapter_no": _first(obj, "chapter_no") or defaults.get("chapter_no"),
            "chapter_title": _first(obj, "chapter_title") if isinstance(_first(obj, "chapter_title"), str) else defaults.get("chapter_title"),
        }
        for k in _LISTY:
            if isinstance(obj.get(k), list):
                yield from _walk(obj[k], inherit)
        for k in ("chapters", "books", "subjects"):
            if isinstance(obj.get(k), list):
                yield from _walk(obj[k], inherit)


def iter_file(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield from _walk(obj, {})
    elif suffix == ".json":
        with path.open(encoding="utf-8") as f:
            yield from _walk(json.load(f), {})


def load_dir(root: str | Path) -> list[dict]:
    """Load + normalise + dedupe every .json/.jsonl under root. Assigns chunk_ref if missing."""
    root = Path(root)
    files = sorted(p for p in root.rglob("*") if p.suffix.lower() in (".json", ".jsonl"))
    out, seen, counters = [], set(), {}
    for p in files:
        for raw, defaults in iter_file(p):
            rec = normalize_record(raw, defaults)
            if rec is None:
                continue
            if not rec["chunk_ref"]:
                key = (rec["class_level"], rec["subject"], rec["chapter_no"])
                counters[key] = counters.get(key, 0) + 1
                rec["chunk_ref"] = f"{key[0]}-{key[1]}-{key[2]}-{counters[key]}"
            if rec["chunk_ref"] in seen:
                continue
            seen.add(rec["chunk_ref"])
            out.append(rec)
    return out
