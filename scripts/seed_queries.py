"""Seed synthetic labelled demo queries (session_id='seed') for teacher analytics.
Usage: python scripts/seed_queries.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# (class_level, subject, topic, sample_questions)
_TOPICS = [
    (5, "math", "গুণ ও ভাগ", [
        "চার অঙ্কের সংখ্যাকে তিন অঙ্কের সংখ্যা দিয়ে গুণ করার নিয়ম কী?",
        "গুণ্য, গুণক ও গুণফল কাকে বলে?",
        "নিঃশেষে বিভাজ্য না হলে ভাজ্য বের করার সূত্র কী?",
    ]),
    (5, "math", "ভগ্নাংশ", [
        "প্রকৃত ও অপ্রকৃত ভগ্নাংশের পার্থক্য কী?",
        "মিশ্র ভগ্নাংশকে কীভাবে অপ্রকৃত ভগ্নাংশে পরিণত করে?",
        "ভগ্নাংশের যোগ করার নিয়ম বুঝিয়ে বলো।",
    ]),
    (5, "bangla", "বৈচিত্র্যময় বাংলাদেশ", [
        "বাংলাদেশে বসবাসকারী ক্ষুদ্র নৃগোষ্ঠীর মাতৃভাষা কী কী?",
        "বাঙালি জাতির ভাষা ও সংস্কৃতির বৈচিত্র্য কেমন?",
        "বাংলাদেশের মানুষের মধ্যে কোন কোন বিষয়ে মিল ও বৈচিত্র্য আছে?",
    ]),
    (5, "science", "আমাদের পরিবেশ", [
        "খাদ্যশৃঙ্খল ও খাদ্যজালের মধ্যে পার্থক্য কী?",
        "উদ্ভিদ ও প্রাণী কীভাবে একে অপরের উপর নির্ভরশীল?",
        "বীজের বিস্তরণ কীভাবে ঘটে?",
    ]),
    (5, "science", "পদার্থ ও শক্তি", [
        "শক্তির বিভিন্ন রূপ কী কী উদাহরণ দাও।",
        "তাপ ও আলোর শক্তি কীভাবে সঞ্চালিত হয়?",
        "পদার্থের তিনটি অবস্থা কী কী?",
    ]),
    (5, "bgs", "বাংলাদেশের ঐতিহাসিক স্থান ও নিদর্শন", [
        "মহাস্থানগড় কোথায় অবস্থিত এবং এটি কেন বিখ্যাত?",
        "লালবাগ কেল্লার ঐতিহাসিক গুরুত্ব কী?",
        "উয়ারী-বটেশ্বরে কী কী নিদর্শন পাওয়া গেছে?",
    ]),
    (5, "islam", "আকাইদ ও ইবাদত", [
        "আকাইদ বলতে কী বোঝায়?",
        "ইসলামে কুরবানির গুরুত্ব ও তাৎপর্য কী?",
    ]),
    (5, "english", "The Champion Girl", [
        "What does Lipi want to be in the future?",
        "How do we use 'want to be' for future professions?",
    ]),
    (4, "science", "জীব ও পরিবেশ", [
        "বেঁচে থাকার জন্য জীবের কী কী প্রয়োজন?",
        "উদ্ভিদ কীভাবে খাদ্য তৈরি করে?",
    ]),
    (3, "bangla", "আমাদের গ্রাম", [
        "আমাদের গ্রাম কবিতায় গ্রামের প্রকৃতি কেমন বর্ণনা করা হয়েছে?",
    ]),
    (2, "math", "যোগ ও বিয়োগ", [
        "হাতে রেখে দুই অঙ্কের যোগ কীভাবে করতে হয়?",
    ]),
    (1, "bangla", "আমার পরিচয়", [
        "নিজের পরিচয় কীভাবে লিখতে হয়?",
    ]),
]

_OFF_SYLLABUS = [
    (5, "science", "ব্ল্যাক হোল", "ব্ল্যাক হোল কীভাবে তৈরি হয়?"),
    (4, "math", "কোয়ান্টাম", "কোয়ান্টাম কম্পিউটিং কীভাবে কাজ করে?"),
    (3, "bangla", "রান্না", "পিৎজা কীভাবে বানাতে হয়?"),
    (5, "bgs", "বিশ্ব রাজনীতি", "ফ্রান্সের বর্তমান প্রেসিডেন্ট কে?"),
]


def build_seed_rows(n: int = 300, rng_seed: int = 42) -> list[dict]:
    """Build deterministic synthetic query rows marked with session_id='seed'."""
    rng = random.Random(rng_seed)
    rows = []
    for _ in range(n):
        refused = rng.random() < 0.18
        if refused and rng.random() < 0.55:
            cls, subj, topic, q = rng.choice(_OFF_SYLLABUS)
        else:
            cls, subj, topic, qs = rng.choice(_TOPICS)
            q = rng.choice(qs)
        top_score = round(rng.uniform(0.12, 0.33), 3) if refused else round(rng.uniform(0.42, 0.92), 3)
        helpful = None
        if not refused and rng.random() < 0.6:
            helpful = rng.random() < 0.8
        rows.append(
            {
                "session_id": "seed",
                "class_level": cls,
                "subject": subj,
                "question": q,
                "topic": topic,
                "top_score": top_score,
                "refused": refused,
                "reason": "low_retrieval" if refused else None,
                "latency_ms": rng.randint(350, 2400),
                "cost_usd": round(rng.uniform(0.0001, 0.0008), 6),
                "helpful": helpful,
            }
        )
    return rows


def seed_db(n: int = 300) -> tuple[int, int]:
    from pathshala.db import get_conn

    rows = build_seed_rows(n=n)
    fb_count = 0
    with get_conn() as c, c.cursor() as cur:
        cur.execute("delete from queries where session_id = %s", ("seed",))
        for r in rows:
            cur.execute(
                """insert into queries(session_id,class_level,subject,question,topic,top_score,refused,reason,latency_ms,cost_usd)
                   values (%(session_id)s,%(class_level)s,%(subject)s,%(question)s,%(topic)s,%(top_score)s,%(refused)s,%(reason)s,%(latency_ms)s,%(cost_usd)s)
                   returning id""",
                r,
            )
            qid = cur.fetchone()["id"]
            if r["helpful"] is not None:
                cur.execute(
                    "insert into feedback(query_id,helpful,comment) values (%s,%s,%s)",
                    (qid, r["helpful"], "seed"),
                )
                fb_count += 1
    return len(rows), fb_count


if __name__ == "__main__":
    q_n, fb_n = seed_db()
    print(f"seeded {q_n} queries and {fb_n} feedback rows (session_id='seed')")

