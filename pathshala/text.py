"""Pure text utils: Bangla normalisation + chunking. No third-party deps (unit-testable)."""
import re
import unicodedata

_ZW_DROP = dict.fromkeys(map(ord, "\u200b\ufeff\u2060"), None)  # keep ZWNJ/ZWJ: Bangla needs them
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_SENT_SPLIT = re.compile(r"(?<=[।?!\.])\s+")
_HEADING = re.compile(r"^\s*(অধ্যায়|Chapter(?![A-Za-z]))", re.IGNORECASE)  # no \b: Bangla marks are not \w


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
