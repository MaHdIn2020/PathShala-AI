"""Loader for NCTB-PrimaryText / NCTB-SchoolText (Mendeley Data, DOI 10.17632/w3hj4m45d9.1, CC BY 4.0).
Documented record fields: class, subject, chapter_no, chapter_title, chunk_id, text (plus optional lang).
Reads .jsonl/.json chunks and joins chapter page ranges from chapters_config_<subject>.json when present."""
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
_DIR_TO_CLASS = {
    "classone": 1,
    "classtwo": 2,
    "classthree": 3,
    "classfour": 4,
    "classfive": 5,
    "classsix": 6,
    "classseven": 7,
    "classeight": 8,
    "classnineten": 9,
}


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


def infer_medium(raw: dict, defaults: dict | None = None, explicit_medium: str | None = None) -> str:
    """Resolve textbook_medium without guessing ambiguous records."""
    if explicit_medium in ("bangla_version", "english_version", "unknown"):
        return explicit_medium
    lang = str(raw.get("lang") or (defaults or {}).get("lang") or "").strip().lower()
    if lang == "en":
        return "english_version"
    if lang == "bn":
        return "bangla_version"
    dm = (defaults or {}).get("textbook_medium")
    if dm in ("bangla_version", "english_version", "unknown"):
        return dm
    return "unknown"


def load_chapter_configs(root: str | Path) -> dict[tuple[int, str, int], dict]:
    """Scan chapters_config_<subject>.json under root -> {(class_level, subject_slug, chapter_no): {page_start, page_end, chapter_title}}."""
    root = Path(root)
    mapping: dict[tuple[int, str, int], dict] = {}
    for cfg_path in sorted(root.rglob("chapters_config_*.json")):
        cls = _DIR_TO_CLASS.get(cfg_path.parent.name.lower()) or to_int(cfg_path.parent.name)
        if cls is None:
            continue
        subj = slug_subject(cfg_path.stem.removeprefix("chapters_config_"))
        try:
            items = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            ch_no = to_int(item.get("chapter_no"))
            if ch_no is None:
                continue
            p_start = to_int(item.get("start_page"))
            p_end = to_int(item.get("end_page"))
            mapping[(cls, subj, ch_no)] = {
                "page_start": p_start,
                "page_end": p_end,
                "chapter_title": item.get("chapter_title"),
            }
    return mapping


def normalize_record(
    raw: dict,
    defaults: dict | None = None,
    *,
    medium: str | None = None,
    curriculum_id: str = "nctb",
    chapter_configs: dict | None = None,
) -> dict | None:
    """Return normalized textbook chunk dict with curriculum identity & optional page range, or None if unusable."""
    d = {**(defaults or {})}
    text = _first(raw, "text")
    if not isinstance(text, str) or not text.strip():
        return None
    cls = to_int(_first(raw, "class")) or to_int(d.get("class"))
    subj = _first(raw, "subject") or d.get("subject")
    if cls is None or not subj:
        return None
    subj_slug = slug_subject(subj)
    ch_no = to_int(_first(raw, "chapter_no"))
    if ch_no is None:
        ch_no = to_int(d.get("chapter_no"))
    title = _first(raw, "chapter_title") or d.get("chapter_title")

    resolved_medium = infer_medium(raw, d, medium)
    ref = _first(raw, "chunk_id")
    ref_str = str(ref).strip() if ref is not None else None
    if ref_str and resolved_medium == "english_version" and not ref_str.startswith("en-"):
        ref_str = f"en-{ref_str}"

    p_start = to_int(raw.get("page_start") or raw.get("start_page"))
    p_end = to_int(raw.get("page_end") or raw.get("end_page"))
    if (p_start is None or p_end is None) and chapter_configs and ch_no is not None:
        cfg_meta = chapter_configs.get((cls, subj_slug, ch_no))
        if cfg_meta:
            p_start = p_start if p_start is not None else cfg_meta.get("page_start")
            p_end = p_end if p_end is not None else cfg_meta.get("page_end")

    return {
        "curriculum_id": d.get("curriculum_id") or curriculum_id,
        "textbook_medium": resolved_medium,
        "edition_year": to_int(raw.get("edition_year")) or 2024,
        "class_level": cls,
        "subject": subj_slug,
        "chapter_no": ch_no,
        "chapter": str(title).strip() if title is not None else None,
        "chunk_ref": ref_str,
        "page_start": p_start,
        "page_end": p_end,
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


def _infer_dir_medium(root: Path, medium: str | None) -> str | None:
    if medium and medium != "auto":
        return medium
    name = str(root).lower()
    if "english" in name:
        return "english_version"
    if "mendeley" in name:
        return "bangla_version"
    return None


def load_dir(root: str | Path, medium: str | None = None, curriculum_id: str = "nctb") -> list[dict]:
    """Load + normalise + dedupe every .json/.jsonl under root (excluding chapters_config_*.json).
    Attaches chapter page ranges and medium-isolated chunk_ref."""
    root = Path(root)
    explicit_medium = _infer_dir_medium(root, medium)
    chapter_configs = load_chapter_configs(root)
    files = sorted(
        p
        for p in root.rglob("*")
        if p.suffix.lower() in (".json", ".jsonl") and not p.name.startswith("chapters_config_")
    )
    out, seen, counters = [], set(), {}
    for p in files:
        for raw, defaults in iter_file(p):
            rec = normalize_record(
                raw,
                defaults,
                medium=explicit_medium,
                curriculum_id=curriculum_id,
                chapter_configs=chapter_configs,
            )
            if rec is None:
                continue
            if not rec["chunk_ref"]:
                key = (rec["textbook_medium"], rec["class_level"], rec["subject"], rec["chapter_no"])
                counters[key] = counters.get(key, 0) + 1
                prefix = "en-" if rec["textbook_medium"] == "english_version" else ""
                rec["chunk_ref"] = f"{prefix}{key[1]}-{key[2]}-{key[3]}-{counters[key]}"
            if rec["chunk_ref"] in seen:
                continue
            seen.add(rec["chunk_ref"])
            out.append(rec)
    return out
