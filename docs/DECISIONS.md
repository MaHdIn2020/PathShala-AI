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

## Blockers
(none yet)
