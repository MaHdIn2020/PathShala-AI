"""Live smoke test against a running API (stdlib only). Checks shape, not answer quality."""
import json
import os
import sys
import urllib.request

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
CLASS = int(os.getenv("SMOKE_CLASS", "3"))  # primary dataset covers classes 1-5


def call(path, body=None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def main():
    assert call("/health").get("ok") is True, "health failed"
    r = call("/ask", {"question": "আমাদের বাংলা বই থেকে একটি প্রশ্ন", "class_level": CLASS, "subject": None})
    for k in ("answer", "citations", "refused", "latency_ms"):
        assert k in r, f"/ask missing key {k}"
    if not r["refused"]:
        assert r["citations"], "answered without citations"
        assert all("chapter_no" in c and "chunk_id" in c for c in r["citations"]), "bad citation shape"
    off = call("/ask", {"question": "How to bake a chocolate cake?", "class_level": CLASS, "subject": None})
    assert off["refused"] is True, "off-syllabus question was NOT refused"
    print("smoke ok")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("SMOKE FAIL:", e)
        sys.exit(1)
