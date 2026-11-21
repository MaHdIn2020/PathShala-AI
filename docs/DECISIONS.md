# Decisions & blockers (agents append; humans edit)
Format: `Dn | date | decision | why`
- D1 | Data = Mendeley NCTB-PrimaryText (DOI 10.17632/w3hj4m45d9.1, CC BY 4.0), classes 1-5 | OCR already done, saves ~1.5 days; PDF/OCR path dropped for MVP
- D7 | Citation = class · subject · chapter_no/title · chunk_ref (no pages in data) | honest to source; page refs removed from UI/claims
- D8 | Contextual retrieval ON only if chunk count/quota allows (T06) | each chunk = 1 fast-LLM call
- D2 | Embeddings = local BAAI/bge-m3 (1024-d) | free, good Bangla, enables "local model" claim (only if actually run)
- D3 | LLM = Gemini Flash via LiteLLM default; verifier may use a different model | cheap + quota-friendly in Antigravity Pro
- D4 | DB = Postgres+pgvector (docker local; Supabase for deploy) | same SQL both places
- D5 | Frontend = Next.js; fallback = single static HTML served by FastAPI if behind schedule on D3 | deadline risk
- D6 | Graph RAG / Neo4j / warehouse = NOT in scope unless T-stretch done; do not claim on form | honesty
- D9 | 2026-11-18 | Contextualisation OFF (`--no-ctx`) for the full ingest; do NOT claim Contextual RAG | T06 sample of 30 chunks: 19 ok, 11 failed (no retry), cost $0.00579 for the 19 (about $0.0003 per chunk, so about $2 for 7,081 chunks, extrapolated). Context text quality was good, but chunk count is above 3,000 and failures need retry logic
- D10 | 2026-11-18 | Ingest scope = classes 1-5 (7,081 chunks after prep); `--max-class 0` ingests all | dataset is NCTB-SchoolText (classes 1-10, 58,872 chunks); see docs/DATA_REPORT.md
- D11 | 2026-11-18 | Models: LLM_MODEL=gemini-3-flash-preview, LLM_FAST_MODEL=gemini-3.5-flash-lite, LLM_VERIFY_MODEL=gemini-3.1-flash-lite | `gemini-flash-latest` returned 503 on repeated tries; these answered a live Bangla call
- D12 | 2026-11-18 | Local bge-m3 loaded in bfloat16, max_seq_length 512, small batches | machine had about 1 GB free RAM and fp32 batch 16 ran out of memory; 50 chunks took 237s
- D13 | 2026-11-19 | Full ingest complete (`--no-ctx`): 7,081 chunks across 33 textbooks (classes 1-5), 7,081 non-null embeddings | ran in 30,127s (~8.4h) on local CPU (`BAAI/bge-m3`, bfloat16); $0 embedding cost; HNSW (`chunks_emb_idx`) + GIN (`chunks_fts_idx`) indexes verified (`explain analyze` FTS scan 10.6ms)
- D14 | 2026-11-19 | Set `MIN_SCORE=0.45` (replacing `0.35`) | 60-question dev calibration (30 in-syllabus `min=0.472, median=0.623, max=0.775`; 30 off-syllabus `min=0.350, median=0.439, max=0.642`): t=0.35 gave 100%/0%, t=0.40 100%/23.3%, t=0.45 100.0% answer_rate / 60.0% pre-LLM refusal_acc (80.0% overall), t=0.50 86.7%/93.3% (90.0% overall). Chose 0.45 to keep answer_rate >=90% while blocking majority of off-syllabus pre-LLM; LLM+verifier handle remaining off-syllabus
- D15 | 2026-11-19 | Keep `RERANK=0` (cross-encoder off) | T10 hand-check on 15 dev answerable questions gave Recall@5 = 14/15 (93.3%) with hybrid vector+FTS RRF alone; loading `bge-reranker-v2-m3` adds latency and RAM pressure on 8 GB machine
- D16 | 2026-11-19 | Frontend deployed to Vercel (`https://web-tanjipsuraitmahdin-gmailcoms-projects.vercel.app`) + DB live on cloud Postgres; backend `Dockerfile`/`render.yaml` ready for Render once human pushes repo (`git push -u origin main`) and sets `NEXT_PUBLIC_API_URL` on Vercel | `vercel --prod --yes` built and aliased cleanly; never `git push` from agent per rules
- D17 | 2026-11-21 | Replace `UNIQUE(class_level, subject)` with `UNIQUE(curriculum_id, textbook_medium, class_level, subject)` and prefix English Version `chunk_ref` with `en-` | Prevents Bangla & English Version collisions; keeps `answer_language` independent of `textbook_medium`
- D18 | 2026-11-21 | Ingest all 43,451 English Version chunks (79 books, Classes 1–10) with FTS + chapter page ranges (`chapters_config_*.json`), plus `BAAI/bge-m3` embeddings on priority demo books (Class 8 Science: 824 chunks; Classes 1–2 Math: 269 chunks) | Avoids >8h CPU embedding block and stays at `196 MB` inside Neon storage while enabling immediate English Version retrieval across Classes 1–10
- D19 | 2026-11-21 | Persist Concept Rescue `learning_events` and EWMA `session_mastery` in PostgreSQL with `event_key` idempotency and `min_group_size=3` teacher privacy suppression | Survives server restarts, prevents duplicate-submission inflation, and avoids identifying small real student cohorts
- D20 | 2026-11-21 | Preserve `eval/golden_set.jsonl` (`n=187`) as historical v1 baseline and add `eval/golden_set_v2.jsonl` (`n=205`) with cross-version leakage & false-refusal metrics | Enables reproducible multi-version benchmarking without conflating different metric definitions
- D21 | 2026-11-21 | Enable 3-DB Postgres sharding (`DATABASE_URL` for Bangla 1–8 + analytics, `DATABASE_URL_BN_SSC` for Bangla 9–10, `DATABASE_URL_EN` for English 1–10) and embed all 102,464 chunks across 211 textbooks with `BAAI/bge-m3` on RTX 4060 (`torch 2.6.0+cu124`) | Fits full Classes 1–10 Bangla + English dense vector + HNSW corpus comfortably across Neon shards (`496 MB` + `425 MB` + `640 MB`) with 100% hybrid vector+FTS coverage

## Blockers
(none)
