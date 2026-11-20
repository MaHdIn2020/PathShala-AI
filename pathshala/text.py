"""Pure text utils: Bangla normalisation, Banglish retrieval expansion & chunking. No third-party deps."""
import re
import unicodedata

_ZW_DROP = dict.fromkeys(map(ord, "\u200b\ufeff\u2060"), None)  # keep ZWNJ/ZWJ: Bangla needs them
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_SENT_SPLIT = re.compile(r"(?<=[।?!\.])\s+")
_HEADING = re.compile(r"^\s*(অধ্যায়|Chapter(?![A-Za-z]))", re.IGNORECASE)  # no \b: Bangla marks are not \w

_BANGLISH_MAP = {
    "khadya shringkhol": "খাদ্যশৃঙ্খল food chain",
    "khadya": "খাদ্য food",
    "shringkhol": "শৃঙ্খল",
    "saloksongshleshon": "সালোকসংশ্লেষণ photosynthesis",
    "salok": "সালোকসংশ্লেষণ",
    "udbhid": "উদ্ভিদ plant",
    "prani": "প্রাণী animal",
    "bhumi": "ভূমি মাটি soil",
    "mati": "মাটি soil",
    "pani": "পানি water",
    "bayu dushon": "বায়ুদূষণ air pollution",
    "bayu": "বায়ু air",
    "dushon": "দূষণ pollution",
    "kosh": "কোষ cell",
    "kos": "কোষ cell",
    "bapon": "ব্যাপন diffusion",
    "obhisrobon": "অভিস্রবণ osmosis",
    "obhisrabon": "অভিস্রবণ osmosis",
    "proshedon": "প্রস্বেদন transpiration",
    "poribesh": "পরিবেশ environment",
    "bastutontro": "বাস্তুতন্ত্র ecosystem",
    "bhognangsho": "ভগ্নাংশ fraction",
    "borgo": "বর্গ square",
    "ayotokhetro": "আয়তক্ষেত্র rectangle",
    "shomikoron": "সমীকরণ equation",
    "protibimbo": "প্রতিবিম্ব reflection",
    "tap": "তাপ heat",
    "bidyut": "বিদ্যুৎ electricity",
    "chumbok": "চুম্বক magnet",
    "shokti": "শক্তি energy",
    "podartho": "পদার্থ matter",
    "omlo": "অম্ল acid",
    "khar": "ক্ষার base",
    "lobon": "লবণ salt",
}

_SPELLING_VARIANTS = {
    "কিভাবে": "কীভাবে",
    "শ্রেণী": "শ্রেণি",
    "পাখী": "পাখি",
    "সূর্য্য": "সূর্য",
    "বায়ু": "বায়ু",
}


def normalize_bangla(text: str, ascii_digits: bool = False) -> str:
    t = unicodedata.normalize("NFC", text or "")
    t = t.translate(_ZW_DROP)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t\u00a0]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    if ascii_digits:
        t = t.translate(_BN_DIGITS)
    return t.strip()


def normalize_for_retrieval(text: str) -> str:
    """Create a retrieval-normalized copy with Banglish & spelling expansions without altering original text."""
    base = normalize_bangla(text, ascii_digits=True)
    if not base:
        return ""
    low = base.lower()
    extras = []
    for k, v in _BANGLISH_MAP.items():
        if re.search(rf"\b{re.escape(k)}\b", low):
            extras.append(v)
    for var, canon in _SPELLING_VARIANTS.items():
        if var in base and canon not in base:
            extras.append(canon)
    return f"{base} {' '.join(extras)}".strip() if extras else base


_SUBJECT_HINTS = {
    "বিজ্ঞান": "science",
    "science": "science",
    "গণিত": "math",
    "অঙ্ক": "math",
    "math": "math",
    "বাংলা": "bangla",
    "bangla": "bangla",
    "ইংরেজি": "english",
    "english": "english",
    "বিশ্বপরিচয়": "bgs",
    "বিশ্বপরিচয়": "bgs",
    "ইসলাম": "islam",
}


def normalize_query(text: str) -> tuple[str, str | None]:
    """Normalize Bangla/ASCII digits & whitespace; also infer optional subject hint if mentioned."""
    q = normalize_bangla(text, ascii_digits=True)
    q = re.sub(r"[।?!,;:\"'()]+$", "", q).strip()
    low = q.lower()
    hint = None
    for kw, slug in _SUBJECT_HINTS.items():
        if kw in low:
            hint = slug
            break
    return q, hint


def _split_long(par: str, max_chars: int) -> list[str]:
    if len(par) <= max_chars:
        return [par]
    out, cur = [], ""
    for s in _SENT_SPLIT.split(par):
        if cur and len(cur) + 1 + len(s) > max_chars:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    final = []
    for o in out:  # hard split if one sentence is still too long
        while len(o) > max_chars:
            final.append(o[:max_chars])
            o = o[max_chars:]
        final.append(o)
    return final


def chunk_pages(pages, max_chars: int = 1200, min_chars: int = 200, chapter: str | None = None) -> list[dict]:
    """pages: iterable of (page_no, text). Returns [{text, page_start, page_end, chapter}].
    Paragraph-aware; a heading line (অধ্যায়/Chapter) starts a new chunk and sets chapter.
    Worked examples are kept whole when they fit in max_chars."""
    units = []  # (page, piece, chapter)
    ch = chapter
    for pno, text in pages:
        for par in re.split(r"\n\s*\n", normalize_bangla(text)):
            par = par.strip()
            if not par:
                continue
            first = par.split("\n", 1)[0].strip()
            if _HEADING.match(first):
                ch = first[:80]
            for piece in _split_long(par, max_chars):
                units.append((pno, piece, ch))

    chunks, cur, size, cur_ch = [], [], 0, None

    def flush():
        if cur:
            chunks.append(
                {
                    "text": "\n\n".join(p for _, p, _ in cur),
                    "page_start": cur[0][0],
                    "page_end": cur[-1][0],
                    "chapter": cur[0][2],
                }
            )
            cur.clear()

    for pno, piece, c in units:
        add = len(piece) + (2 if cur else 0)
        if cur and (size + add > max_chars or c != cur_ch):
            flush()
            size, add = 0, len(piece)
        cur.append((pno, piece, c))
        cur_ch = c
        size += add
    flush()

    if len(chunks) >= 2:
        last, prev = chunks[-1], chunks[-2]
        if (
            len(last["text"]) < min_chars
            and last["chapter"] == prev["chapter"]
            and len(prev["text"]) + 2 + len(last["text"]) <= max_chars * 1.25
        ):
            prev["text"] += "\n\n" + last["text"]
            prev["page_end"] = last["page_end"]
            chunks.pop()
    return chunks
