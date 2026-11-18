# SPEC — PathShala AI (v1, MVP)
**One line:** Ask an NCTB primary textbook question in Bangla → cited answer (class, subject, chapter, source chunk) or an honest "not in textbook".
**Data:** NCTB-PrimaryText, Mendeley Data, DOI 10.17632/w3hj4m45d9.1, CC BY 4.0 (OCR-extracted, chunked by chapter; fields class, subject, chapter_no, chapter_title, chunk_id, text; NO page numbers).
**MVP scope:** primary classes 1–5, all subjects in the dataset. Architecture can add classes 6–12 later (PDF path, `text.chunk_pages`).
**Non-goals:** accounts/login, payments, native app, fine-tuning, English-medium books.

## Users
Student (text/voice/photo question) · Teacher (read-only topic dashboard).

## API (FastAPI, pathshala/api.py)
| Method | Path | Body → Response |
|---|---|---|
| GET | /health | → {ok:true} |
| POST | /ask | {question, class_level 1-12 (UI offers 1-5), subject?, session_id?} → {answer, steps[], citations[{chunk_id,chunk_ref,book,class_level,subject,chapter_no,chapter,snippet}], confidence, refused, reason, top_score, topic, latency_ms, cost_usd, cached, query_id} |
| POST | /ask-image | multipart image + class_level → same as /ask (T12) |
| POST | /practice | {chunk_ids[]} → {questions[{q,a,chunk_id,level}]} (T13) |
| POST | /search | same body as /ask → chunks |
| POST | /baseline | same body → plain-LLM answer (eval only) |
| POST | /feedback | {query_id, helpful, comment?} → {ok} |
| GET | /cite/{chunk_id} | → source chunk |
| GET | /teacher/topics | → [{class_level,subject,topic,n,refused}] |
| GET | /teacher/summary | richer aggregates (T24) |

## Data model: db/schema.sql (textbooks unique(class,subject), chunks[chunk_ref, chapter_no, chapter, embedding vector(1024), fts], queries, feedback, eval_runs).
**Limitations to state honestly:** OCR noise, weaker math, no page numbers (citation = chapter + chunk), primary only.

## Pipeline (pathshala/pipeline.py)
rewrite (fast LLM) → hybrid retrieve top-30 (vector+FTS, RRF) → [optional rerank] top-5 → gate (`top sim < MIN_SCORE` ⇒ refuse) → answer (JSON) → clean_citations (drop unknown ids, rebuild metadata) → verifier (cheap LLM, PASS/FAIL) → respond. Any failure ⇒ refuse with reason.

## Acceptance criteria (all must be demonstrable)
- AC1 `bash scripts/verify.sh` GREEN from fresh clone.
- AC2 In-syllabus question → answer in Bangla with ≥1 citation whose chapter is correct (manual check on 10 questions: ≥8).
- AC3 Off-syllabus question → refusal (smoke test asserts).
- AC4 Citation chip (শ্রেণি · বিষয় · অধ্যায়) expands snippet from the real chunk.
- AC5 Photo question works (text extracted → answered).
- AC6 Teacher page shows topic counts (seed data labelled as demo).
- AC7 Eval: golden set ≥150 answerable + ≥30 off-syllabus; RAG vs baseline results JSON + chart.
- AC8 p95 latency measured and reported; cost/query reported.
- AC9 Deployed URL works on a phone; backup tunnel documented.
- AC10 README complete; repo public; no secrets; PDFs not committed.
- AC11 Custom MCP server callable from Antigravity (T27).
- AC12 Video 2–3 min uploaded.

## Safety/privacy
No PII collected; random session id; photos not stored; logs 30 days; "AI can err — textbook is the authority" notice; self-harm keywords → calm message + suggest talking to a trusted adult/helpline (T19).
