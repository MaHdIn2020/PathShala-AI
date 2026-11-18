"""Generate golden set draft for evaluation.
Loads chunks from classes 1-5, generates ~150 answerable Qs + ~30 off-syllabus Qs.
Usage: python eval/generate_golden_set.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.mendeley import load_dir
from ingest.prepare import prepare
from pathshala.config import get_config
from pathshala.llm import chat_json
from pathshala.pipeline import load_prompt

OFF_SYLLABUS = [
    (1, "bangla", "পিৎজা কীভাবে বানাতে হয়?"),
    (1, "math", "ইউরোপের সবচেয়ে বড় নদী কোনটি?"),
    (2, "bangla", "রকেট কীভাবে মহাকাশে যায়?"),
    (2, "english", "How to fix a motorcycle engine?"),
    (3, "science", "কালো গহ্বর বা ব্ল্যাক হোল কীভাবে তৈরি হয়?"),
    (3, "math", "শেয়ার বাজারে টাকা বিনিয়োগের উপায় কী?"),
    (3, "bgs", "ফ্রান্সের বর্তমান প্রেসিডেন্টের নাম কী?"),
    (3, "islam", "পাইথনে ফর-লুপ কীভাবে কাজ করে?"),
    (4, "bangla", "জাপানি ভাষা সহজে শেখার নিয়ম কি?"),
    (4, "math", "কোয়ান্টাম কম্পিউটিং কী?"),
    (4, "science", "আইফোনের নতুন মডেল কবে রিলিজ হবে?"),
    (4, "english", "What is the capital of Argentina?"),
    (4, "bgs", "প্রথম বিশ্বযুদ্ধ কত সালে শুরু হয়েছিল?"),
    (4, "islam", "চাঁদে পানির সন্ধান পাওয়া গেছে কি?"),
    (4, "hindu_religion", "সুপারসনিক বিমানের গতিবেগ কত?"),
    (5, "bangla", "ড্রাইভিং লাইসেন্স পাওয়ার বয়স কত?"),
    (5, "math", "পাইথন দিয়ে মেশিন লার্নিং কীভাবে শিখব?"),
    (5, "science", "চাঁদের মাটিতে কোনো উদ্ভিদ জন্মায় কি না?"),
    (5, "bgs", "ইউক্রেন যুদ্ধের মূল কারণ কী?"),
    (5, "english", "How to write a smart contract on Ethereum?"),
    (5, "islam", "রোবট কি মানুষের চেয়ে বুদ্ধিমান হতে পারে?"),
    (5, "hindu_religion", "মঙ্গল গ্রহে মানুষ পাঠানোর পরিকল্পনা কি?"),
    (5, "buddhist_religion", "কম্পিউটার ভাইরাস কীভাবে তৈরি হয়?"),
    (5, "christian_religion", "আন্তর্জাতিক মহাকাশ স্টেশনের ওজন কত?"),
    (5, "science", "ক্যানসারের আধুনিক চিকিৎসাপদ্ধতি কী?"),
    (5, "math", "স্টক এক্সচেঞ্জের সূচক কীভাবে হিসাব করে?"),
    (5, "bangla", "বিশ্বের সবচেয়ে দ্রুতগতির ট্রেন কোনটি?"),
    (5, "bgs", "আমাজনের গভীর জঙ্গলে কী কী প্রাণী আছে?"),
    (5, "science", "সূর্যের পৃষ্ঠের তাপমাত্রা কত ডিগ্রি সেলসিয়াস?"),
    (5, "english", "How do airplanes generate aerodynamic lift?"),
    (5, "math", "বিটকয়েন মাইনিং কীভাবে করা হয়?"),
    (5, "bangla", "আন্তর্জাতিক ফুটবল বিশ্বকাপের ইতিহাস কী?"),
]


_META_QS = {"শ্রেণি কত?", "বিষয় কী?", "বিষয় কী?", "অধ্যায়ের নাম কী?", "অধ্যায়ের নাম কী?"}


def _gen_for_chunk(system: str, chunk: dict, models: list[str]) -> list[dict]:
    prompt_user = f"PASSAGE:\nঅধ্যায়: {chunk.get('chapter', '')}\n{chunk['text'][:1500]}"
    for model in models:
        try:
            res, _ = chat_json(system, prompt_user, model, max_tokens=500)
            items = res.get("items") or []
            if items:
                return items
        except Exception as e:
            print(f"model {model} failed on {chunk['chunk_ref']}: {str(e)[:120]}", file=sys.stderr)
    return []


def topup_and_clean(min_answerable: int = 155, out_file: str = "eval/golden_set.jsonl") -> tuple[int, int]:
    """Filter trivial meta-questions, top up answerable items >= min_answerable, and append OFF_SYLLABUS."""
    cfg = get_config()
    out_path = Path(out_file)
    existing = []
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answerable") and row.get("question", "").strip() not in _META_QS:
                existing.append(row)

    used_refs = {ref for r in existing for ref in (r.get("gold_refs") or [])}
    models = list(dict.fromkeys([cfg.llm_fast_model, "gemini/gemini-flash-lite-latest", "gemini/gemini-3.1-flash-lite"]))

    if len(existing) < min_answerable:
        recs, _ = prepare(load_dir("data/raw/mendeley"), max_class=5)
        eligible = [
            r for r in recs
            if len(r["text"]) >= 180 and r.get("chapter_no") is not None and r["chunk_ref"] not in used_refs
        ]
        step = max(1, len(eligible) // 80)
        sampled = eligible[::step]
        system = load_prompt("eval_qa_gen")

        for chunk in sampled:
            if len(existing) >= min_answerable:
                break
            for qa in _gen_for_chunk(system, chunk, models):
                q = (qa.get("question") or "").strip()
                kws = [str(k).strip() for k in qa.get("keywords") or [] if str(k).strip()]
                if not q or not kws or q in _META_QS:
                    continue
                existing.append(
                    {
                        "id": "",
                        "class_level": chunk["class_level"],
                        "subject": chunk["subject"],
                        "question": q,
                        "answerable": True,
                        "keywords": kws,
                        "gold_chapters": [chunk["chapter_no"]],
                        "gold_refs": [chunk["chunk_ref"]],
                    }
                )
                if len(existing) >= min_answerable:
                    break

    all_rows = []
    idx = 1
    for row in existing:
        row["id"] = f"q_{idx:03d}"
        all_rows.append(row)
        idx += 1

    for cls, subj, q in OFF_SYLLABUS:
        all_rows.append(
            {
                "id": f"q_{idx:03d}",
                "class_level": cls,
                "subject": subj,
                "question": q,
                "answerable": False,
                "keywords": [],
                "gold_chapters": [],
                "gold_refs": [],
            }
        )
        idx += 1

    with out_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(all_rows)} rows ({len(existing)} answerable + {len(OFF_SYLLABUS)} off-syllabus) to {out_path}")
    return len(existing), len(OFF_SYLLABUS)


if __name__ == "__main__":
    topup_and_clean()

