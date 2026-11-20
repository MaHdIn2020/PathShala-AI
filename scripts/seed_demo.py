"""Idempotent demo seeder for Concept Rescue learning events & session mastery (session_id='seed').
Usage: python scripts/seed_demo.py
All rows are explicitly marked with session_id='seed' so the Teacher Dashboard labels them as Demo Data."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pathshala.db import get_conn
from pathshala.mastery import difficulty_for_mastery, update_ewma

_SEED_EVENTS = [
    # Class 8 Science (English Version) — Diffusion, Osmosis and Transpiration (primary demo hotspot)
    ("seed-cr-1", "nctb", "english_version", 8, "science", "Diffusion, Osmosis and Transpiration", "Distinguish diffusion from osmosis", "cr-demo-1", "B", False, "Likely misconception: confusing general molecular diffusion with water movement across a semi-permeable membrane"),
    ("seed-cr-2", "nctb", "english_version", 8, "science", "Diffusion, Osmosis and Transpiration", "Distinguish diffusion from osmosis", "cr-demo-1", "B", False, "Likely misconception: confusing general molecular diffusion with water movement across a semi-permeable membrane"),
    ("seed-cr-3", "nctb", "english_version", 8, "science", "Diffusion, Osmosis and Transpiration", "Distinguish diffusion from osmosis", "cr-demo-1", "B", False, "Likely misconception: confusing general molecular diffusion with water movement across a semi-permeable membrane"),
    ("seed-cr-4", "nctb", "english_version", 8, "science", "Diffusion, Osmosis and Transpiration", "Explain stomatal transpiration", "cr-demo-2", "C", False, "Likely misconception: assuming root hair absorption and leaf transpiration are the same process"),
    ("seed-cr-5", "nctb", "english_version", 8, "science", "Diffusion, Osmosis and Transpiration", "Distinguish diffusion from osmosis", "cr-demo-1b", "A", True, None),
    ("seed-cr-6", "nctb", "english_version", 8, "science", "Diffusion, Osmosis and Transpiration", "Distinguish diffusion from osmosis", "cr-demo-1b", "A", True, None),
    # Class 8 Science (English Version) — Acid, Base and Salt
    ("seed-cr-7", "nctb", "english_version", 8, "science", "Acid, Base and Salt", "Identify litmus indicator color change", "cr-demo-3", "C", False, "Likely misconception: reversing blue-to-red acid litmus color change with base behavior"),
    ("seed-cr-8", "nctb", "english_version", 8, "science", "Acid, Base and Salt", "Identify litmus indicator color change", "cr-demo-3", "C", False, "Likely misconception: reversing blue-to-red acid litmus color change with base behavior"),
    ("seed-cr-9", "nctb", "english_version", 8, "science", "Acid, Base and Salt", "Identify litmus indicator color change", "cr-demo-3b", "A", True, None),
    ("seed-cr-10", "nctb", "english_version", 8, "science", "Acid, Base and Salt", "Define neutral salt", "cr-demo-4", "D", True, None),
    # Class 5 Science (Bangla Version) — আমাদের পরিবেশ
    ("seed-cr-11", "nctb", "bangla_version", 5, "science", "আমাদের পরিবেশ", "খাদ্যশৃঙ্খলের প্রবাহ", "cr-demo-5", "B", False, "সম্ভাব্য ভুল ধারণা: খাদ্যশৃঙ্খলে উৎপাদক (সবুজ উদ্ভিদ) ও প্রথম শ্রেণির খাদকের অবস্থান গুলিয়ে ফেলা"),
    ("seed-cr-12", "nctb", "bangla_version", 5, "science", "আমাদের পরিবেশ", "খাদ্যশৃঙ্খলের প্রবাহ", "cr-demo-5", "B", False, "সম্ভাব্য ভুল ধারণা: খাদ্যশৃঙ্খলে উৎপাদক (সবুজ উদ্ভিদ) ও প্রথম শ্রেণির খাদকের অবস্থান গুলিয়ে ফেলা"),
    ("seed-cr-13", "nctb", "bangla_version", 5, "science", "আমাদের পরিবেশ", "খাদ্যশৃঙ্খলের প্রবাহ", "cr-demo-5b", "A", True, None),
    # Class 5 Math (Bangla Version) — ভগ্নাংশ
    ("seed-cr-14", "nctb", "bangla_version", 5, "math", "ভগ্নাংশ", "প্রকৃত ও অপ্রকৃত ভগ্নাংশ", "cr-demo-6", "C", False, "সম্ভাব্য ভুল ধারণা: প্রকৃত ভগ্নাংশে লব হরের চেয়ে বড় ভেবে ভুল করা"),
    ("seed-cr-15", "nctb", "bangla_version", 5, "math", "ভগ্নাংশ", "প্রকৃত ও অপ্রকৃত ভগ্নাংশ", "cr-demo-6", "C", False, "সম্ভাব্য ভুল ধারণা: প্রকৃত ভগ্নাংশে লব হরের চেয়ে বড় ভেবে ভুল করা"),
    ("seed-cr-16", "nctb", "bangla_version", 5, "math", "ভগ্নাংশ", "প্রকৃত ও অপ্রকৃত ভগ্নাংশ", "cr-demo-6b", "A", True, None),
    ("seed-cr-17", "nctb", "bangla_version", 5, "math", "ভগ্নাংশ", "ভগ্নাংশের যোগ", "cr-demo-7", "A", True, None),
]


def seed_concept_rescue_demo() -> dict:
    buckets: dict[tuple[str, str, int, str, str], dict] = {}
    with get_conn() as c, c.cursor() as cur:
        cur.execute("delete from learning_events where session_id = 'seed'")
        cur.execute("delete from session_mastery where session_id = 'seed'")
        for row in _SEED_EVENTS:
            ek, curr, med, cls, subj, chap, obj, qid, sel, ok, misc = row
            cur.execute(
                """insert into learning_events(
                       event_key, session_id, curriculum_id, textbook_medium, class_level, subject, chapter,
                       learning_objective, event_type, question_id, selected_option, is_correct, likely_misconception
                   ) values (%s,'seed',%s,%s,%s,%s,%s,%s,'concept_rescue_check',%s,%s,%s,%s)""",
                (ek, curr, med, cls, subj, chap, obj, qid, sel, ok, misc),
            )
            key = (curr, med, cls, subj, chap)
            st = buckets.setdefault(key, {"mastery": 0.5, "attempts": 0, "correct": 0, "last_misc": None})
            st["mastery"] = update_ewma(st["mastery"], ok)
            st["attempts"] += 1
            st["correct"] += 1 if ok else 0
            if misc:
                st["last_misc"] = misc

        for (curr, med, cls, subj, chap), st in buckets.items():
            cur.execute(
                """insert into session_mastery(
                       session_id, curriculum_id, textbook_medium, class_level, subject, chapter,
                       mastery, attempts, correct, last_misconception, updated_at
                   ) values ('seed',%s,%s,%s,%s,%s,%s,%s,%s,%s,now())""",
                (curr, med, cls, subj, chap, st["mastery"], st["attempts"], st["correct"], st["last_misc"]),
            )
    return {
        "events_seeded": len(_SEED_EVENTS),
        "chapters_seeded": len(buckets),
        "difficulties": {k[4]: difficulty_for_mastery(v["mastery"]) for k, v in buckets.items()},
    }


if __name__ == "__main__":
    print(seed_concept_rescue_demo())
