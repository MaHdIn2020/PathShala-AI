# PathShala AI (পাঠশালা AI)
Bangla tutor grounded in NCTB primary textbooks (classes 1-5). Ask by text/voice/photo → answer + class/subject/chapter citation with source snippet, or an honest "not in textbook".

> Status: **kit/scaffold**. Core logic (chunking, fusion, grounding, citation cleaning, eval metrics) is implemented and unit-tested. Ingestion, UI, deploy are built by Antigravity from `docs/TASKS.md`.

## Start in Antigravity (5 steps)
1. Unzip, open this folder as a workspace. 2. `bash scripts/setup.sh` and put `GEMINI_API_KEY` in `.env`.
3. Download the dataset (link below), unzip into `data/raw/mendeley/`, run `python scripts/inspect_dataset.py data/raw/mendeley`. 4. New chat → paste `ANTIGRAVITY_MASTER_PROMPT.md`.
5. Every next task: new chat → `/next`. Read `docs/ANTIGRAVITY_GUIDE.md` first (quota tips).

## Commands
`make db` · `make api` · `make web` · `make verify` · `make eval`

## Architecture
ingest (NCTB-PrimaryText JSON → normalise → contextualise → bge-m3 embed) → Postgres+pgvector → hybrid search (vector + FTS, RRF) → grounded answer (LiteLLM, JSON) → citation clean → verifier → FastAPI → Next.js UI. Teacher dashboard from query logs. Custom MCP server `nctb-corpus`.

## Layout
`pathshala/` core · `ingest/` · `eval/` · `mcp_server/` · `web/` · `prompts/` · `db/schema.sql` · `scripts/` · `tests/` · `docs/` · `.agents/` (rules, skills, workflows) · `AGENTS.md`

## MCP Server (nctb-corpus)
Custom FastMCP stdio server in `mcp_server/server.py` (config snippet in `mcp_server/mcp_config.snippet.json`). Run directly with `python -m mcp_server.server`.
- **Tools (read-only):**
  - `search_textbook(query, class_level, subject=None, k=5)` — hybrid vector + FTS RRF search over NCTB textbook chunks.
  - `list_chapters(book_id)` — chapter numbers, titles, and chunk counts for a textbook.
  - `get_chapter(book_id, chapter_no)` — all chunks in a textbook chapter.
  - `explain_citation(chunk_id)` — full source chunk and metadata (`class_level`, `subject`, `chapter`, `chunk_ref`, `text`) behind a citation.
- **Database permissions:** use a read-only Postgres role in production:
  `create role mcp_ro login password '...'; grant select on chunks, textbooks to mcp_ro;`
- **Build disclosure:** custom `nctb-corpus` MCP server is provided in `mcp_server/`; no external third-party MCP servers were enabled during the build.

## Honesty
No metric in this repo is real until produced by `make eval`. See `docs/SUBMISSION_MAP.md` for what may be claimed.
## Data/licence
**Dataset:** Badar, Mir Hossain Ahmed, Pervaj Ahmed Tuhin. *NCTB-PrimaryText: A Curriculum-Aligned Textbook Chunk Dataset for Bangla and English Primary Education.* Mendeley Data, V1, 2026. DOI 10.17632/w3hj4m45d9.1. Licence CC BY 4.0 (https://data.mendeley.com/datasets/w3hj4m45d9/1). Not redistributed here.
**Limits:** OCR noise (esp. math), no page numbers, primary classes only. Code: MIT.
