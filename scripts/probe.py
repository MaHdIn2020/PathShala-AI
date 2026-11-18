"""Retrieval probe CLI. Usage:
  python scripts/probe.py "<question>" <class_level> [subject]
  python scripts/probe.py    # runs 10 default NCTB primary questions
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_QUESTIONS = [
    ("বাংলাদেশে বসবাসকারী ক্ষুদ্র নৃগোষ্ঠীর মাতৃভাষা কী কী?", 5, "bangla"),
    ("চার অঙ্কের সংখ্যাকে তিন অঙ্কের সংখ্যা দিয়ে গুণ করার নিয়ম কী?", 5, "math"),
    ("খাদ্যশৃঙ্খল ও খাদ্যজালের মধ্যে পার্থক্য কী?", 5, "science"),
    ("মহাস্থানগড় কোথায় অবস্থিত?", 5, "bgs"),
    ("ইসলামে কুরবানির গুরুত্ব ও তাৎপর্য কী?", 5, "islam"),
    ("What does Lipi want to be in the future?", 5, "english"),
    ("উদ্ভিদ কীভাবে খাদ্য তৈরি করে?", 4, "science"),
    ("আমাদের গ্রাম কবিতায় কী বলা হয়েছে?", 3, "bangla"),
    ("হাতে রেখে যোগ করার নিয়ম কী?", 2, "math"),
    ("প্রথম শ্রেণির আমার পরিচয় পাঠে কী লেখা আছে?", 1, "bangla"),
]


def format_probe_results(question: str, class_level: int, subject: str | None, chunks: list[dict]) -> str:
    """Format top-5 retrieval rows (id, chunk_ref, sim, chapter, 80-char snippet)."""
    lines = [f"Q [class={class_level}, subject={subject or 'all'}]: {question}"]
    if not chunks:
        lines.append("  (no results)")
        return "\n".join(lines)
    for idx, c in enumerate(chunks[:5], start=1):
        snippet = (c.get("text") or "").replace("\n", " ")[:80]
        lines.append(
            f"  {idx}. id={c.get('id')} ref={c.get('chunk_ref')} sim={c.get('sim', 0.0):.3f} "
            f"ch={c.get('chapter_no')}:{c.get('chapter') or '-'} | {snippet}"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    from pathshala.retrieval import search

    args = sys.argv[1:] if argv is None else argv
    if args:
        q = args[0]
        cls = int(args[1]) if len(args) > 1 else 5
        subj = args[2] if len(args) > 2 else None
        print(format_probe_results(q, cls, subj, search(q, cls, subj, k=5)))
        return 0

    for q, cls, subj in DEFAULT_QUESTIONS:
        print(format_probe_results(q, cls, subj, search(q, cls, subj, k=5)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

