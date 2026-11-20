# PathShalaAI — Demo Script & Network Fallback Guide

## Primary 3-Minute Judge Demo Journey (Concept Rescue + Cross-Version Isolation)

### Pre-Demo Check
1. Start Backend API: `uvicorn pathshala.api:app --host 0.0.0.0 --port 8000` (check `GET /health/ready` returns `{"ok": true, "db": "ready"}`).
2. Start Frontend: `npm --prefix web run dev` (open `http://localhost:3000` or deployed Vercel URL).

### Step-by-Step Script (9 Steps)
1. **Select NCTB English Version, Class 8, Science:**
   - In the bottom composer bar, pick `Textbook: English Version`, `শ্রেণি 8`, `Science` (or click the first starter prompt card `"EN Version · Class 8 · Science → বাংলায় ব্যাখ্যা"`).
2. **Set Explanation Language to Bangla:**
   - Ensure `ব্যাখ্যার ভাষা: বাংলা` is selected—demonstrating that textbook medium (`english_version`) and explanation language (`bn`) are completely separate.
3. **Ask a Grounded Textbook Question:**
   - Submit: `"What is diffusion and how does it work in plants?"`
4. **Inspect Verified Citations & Page Ranges:**
   - Show the Bangla explanation grounded strictly in the English Version Class 8 Science textbook.
   - Click the `[EN] Class 8 · science · Ch 3: Diffusion, Osmosis and Transpiration · p.30-39` citation chip to show the verbatim textbook chunk (`en-8-Science-3-...`) and verified chapter page range (`pp. 30-39`).
5. **Trigger Concept Rescue Check:**
   - Click `"🎯 ধারণা যাচাই করো (Concept Check)"` to generate a 4-option diagnostic MCQ grounded in the same textbook chunk.
6. **Submit an Incorrect Answer Intentionally:**
   - Pick a distractor option (e.g., confusing diffusion with osmosis).
   - Point out:
     - Warm, non-shaming feedback.
     - **Likely Misconception (`সম্ভাব্য ভুল ধারণা`)** badge tied cautiously to the observed choice.
     - **Simpler Grounded Re-teaching Explanation (`সহজ ভাষায় পুনরায় ব্যাখ্যা`)** with verified page range (`pp. 30-39`).
     - **Fresh Follow-up Practice Question (`নতুন অনুশীলন প্রশ্ন`)** targeting the same learning objective.
7. **Answer the Fresh Question Correctly:**
   - Select the correct option on the follow-up MCQ.
8. **Show Persisted Mastery Update:**
   - Point to the live **Estimated Practice Mastery (EWMA)** bar updating immediately (stored idempotently in PostgreSQL `learning_events` and `session_mastery`, surviving page refresh and backend restarts).
9. **Open Teacher Learning-Gap Dashboard (`/teacher`):**
   - Click `📊 শিক্ষক ড্যাশবোর্ড` (`/teacher`).
   - Show the **Concept Rescue Learning Gaps** table (`EN Version · Class 8 · science · Diffusion, Osmosis and Transpiration`) with sample count (`n=... attempts`) beside incorrect rate, **Recurring Likely Misconceptions**, and the explicit **Demo Data (`ডেমো ডেটা`)** + **Privacy Threshold (`min_group_size=3`)** notices.

### Optional Safety & Refusal Checks (30 seconds)
- Switch to `English Version · Class 1` -> show only `Mathematics` is selectable (unavailable subjects cannot be queried, and direct API calls return `unavailable_curriculum`).
- Ask `"আমি মরে যেতে চাই"` or `"ami more jete chai"` -> instant pre-LLM response with Child Helpline **1098**, never logged to `queries`.

---

## Network / LLM Provider Fallback Plan
If internet/Gemini API fails during live judging:
1. **Local FTS + Cached Demo Proof:** Verify Postgres readiness via `GET /health/ready` and run `POST /search` on `"diffusion osmosis"` (Class 8, `english_version`) to show sub-second live retrieval + page range provenance without calling any external LLM.
2. **Offline Unit & Safety Proof:** Run `python -m unittest discover -s tests -t . -q` (`100` offline tests) and `python scripts/redteam.py` (`50/50 PASS`).
3. **Static Teacher & Eval Evidence:** Present `/teacher` pre-seeded demo analytics (`scripts/seed_demo.py`) and `docs/eval_chart.png` + `docs/EVAL_REPORT.md`.
