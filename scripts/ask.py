"""End-to-end tutor pipeline CLI. Usage:
  python scripts/ask.py "<question>" <class_level> [subject]
  python scripts/ask.py    # runs 10 default NCTB primary questions
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_QUESTIONS = [
    ("বাংলাদেশে বসবাসকারী ক্ষুদ্র নৃগোষ্ঠীর মাতৃভাষা কী কী?", 5, "bangla", 1),
    ("গুণ্য, গুণক ও গুণফল কাকে বলে?", 5, "math", 1),
    ("খাদ্যশৃঙ্খল কাকে বলে?", 5, "science", 1),
    ("লালবাগ কেল্লা কোথায় অবস্থিত?", 5, "bgs", 6),
    ("ইসলামে কুরবানির গুরুত্ব কী?", 5, "islam", 1),
    ("What does Lipi want to be in the future?", 5, "english", 14),
    ("জীব ও পরিবেশের মধ্যে সম্পর্ক কী?", 4, "science", 1),
    ("একতাই বল গল্পের মূল শিক্ষা কী?", 3, "bangla", 1),
    ("দুই অঙ্কের সংখ্যা কীভাবে যোগ করে?", 2, "math", 2),
    ("আমার পরিচয় পাঠে শিক্ষার্থী কোন শ্রেণিতে পড়ে?", 1, "bangla", 1),
]


def format_ask_result(question: str, class_level: int, res: dict) -> str:
    """Format answer(), refusal reason, metrics, and rebuilt citations."""
    lines = [
        f"Q [class={class_level}]: {question}",
        f"  refused={res.get('refused')} reason={res.get('reason')} top_score={res.get('top_score')} "
        f"latency={res.get('latency_ms')}ms cost=${res.get('cost_usd', 0.0):.5f}",
        f"  answer: {res.get('answer', '')}",
    ]
    for c in res.get("citations") or []:
        lines.append(
            f"  cite: শ্রেণি {c.get('class_level')} · {c.get('subject')} · "
            f"অধ্যায় {c.get('chapter_no')}: {c.get('chapter') or '-'} ({c.get('chunk_ref')})"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    from pathshala.pipeline import answer

    args = sys.argv[1:] if argv is None else argv
    if args and args[0] != "--batch":
        q = args[0]
        cls = int(args[1]) if len(args) > 1 else 5
        subj = args[2] if len(args) > 2 else None
        print(format_ask_result(q, cls, answer(q, cls, subj)))
        return 0

    matched = 0
    for q, cls, subj, exp_ch in DEFAULT_QUESTIONS:
        res = answer(q, cls, subj)
        print(format_ask_result(q, cls, res))
        cites_ch = {c.get("chapter_no") for c in res.get("citations") or []}
        ok = (not res.get("refused")) and (exp_ch in cites_ch)
        matched += int(ok)
        print(f"  expected_chapter={exp_ch} hit={ok}\n")
    print(f"chapter match: {matched}/{len(DEFAULT_QUESTIONS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

