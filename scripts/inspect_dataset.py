"""Print the real shape of the downloaded dataset. Usage: python scripts/inspect_dataset.py data/raw/mendeley"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingest.mendeley import load_dir  # noqa: E402

root = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/mendeley")
files = sorted(p for p in root.rglob("*") if p.suffix.lower() in (".json", ".jsonl"))
print(f"files: {len(files)}")
for p in files[:5]:
    print(" ", p.relative_to(root))
    head = p.read_text(encoding="utf-8")[:400].replace("\n", " ")
    print("   head:", head)
recs = load_dir(root)
print(f"usable records: {len(recs)}")
if recs:
    print("by class:", dict(sorted(Counter(r["class_level"] for r in recs).items())))
    print("by subject:", dict(Counter(r["subject"] for r in recs)))
    print("chapters:", len({(r['class_level'], r['subject'], r['chapter_no']) for r in recs}))
    lens = sorted(len(r["text"]) for r in recs)
    print(f"chars min/median/p95/max: {lens[0]}/{lens[len(lens)//2]}/{lens[int(.95*(len(lens)-1))]}/{lens[-1]}")
    print("sample:", json.dumps(recs[0], ensure_ascii=False)[:400])
else:
    print("NO usable records: loader aliases in ingest/mendeley.py need updating (see keys in head above).")
