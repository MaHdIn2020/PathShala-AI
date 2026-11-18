# PathShala AI — agent rules (always on)
Goal: Bangla NCTB primary-textbook tutor. RAG over the Mendeley NCTB-PrimaryText dataset (classes 1-5), cited answers (class/subject/chapter/chunk — dataset has NO page numbers), refuse if not in book.
Deadline: 20 Nov. Speed + working demo > polish. Spec: docs/SPEC.md. Work queue: docs/TASKS.md. Decisions: docs/DECISIONS.md.

## Loop (every task)
1. Read ONLY: this file, the task in docs/TASKS.md, the matching skill in .agents/skills/, files the task names.
2. Implement smallest change that meets "Done when".
3. Run `bash scripts/verify.sh`. RED -> fix -> rerun. Max 3 fix rounds, then log blocker in docs/DECISIONS.md, mark task BLOCKED, move on.
4. Add/adjust a unit test for any new pure logic (tests/, stdlib unittest, no network/DB).
5. Tick the task in docs/TASKS.md. Commit per "Git" below.
6. Reply ≤5 lines: `DONE Txx` + files changed + verify result + next task id. No recap, no code dump.

## Hard rules
- Answers MUST come from retrieved chunks only. Citations are rebuilt from chunk metadata (pathshala/pipeline.py clean_citations). Never let the model invent a source.
- Never fabricate metrics, accuracy numbers, model names, links. Report only measured results (eval/results.json).
- No secrets in git. Keys only in .env. Never print .env.
- Bangla UI strings default; code/comments English.
- Data = Mendeley NCTB-PrimaryText (CC BY 4.0) in data/raw/mendeley/ (gitignored). Keep attribution in README. Never invent page numbers.
- Prefer stdlib + deps in requirements.txt. Add a dep only if a task needs it; note it in DECISIONS.md.

## Git (hooks in .githooks enforce this)
- Commit each working change on its own, message like a person wrote it: short, lowercase, imperative, ≤60 chars, no task ids, no `feat:`/`fix:` prefixes, no emoji, no tool/AI names, no Co-authored-by or signature trailers, no body unless truly needed. Good: `add hybrid search with rrf`, `handle empty chapter titles in loader`, `fix refusal threshold for off-syllabus questions`, `show citation chips under the answer`.
- Small logical commits (one idea each). Never one giant commit. Never amend or rewrite pushed history.
- Stage explicit paths: `git status --short`, then `git add <paths>`. Never `git add -A` / `git add .`.
- Only repo-worthy files: source, tests, prompts/, db/, eval/golden_set.jsonl, eval chart/report, README, docs/SPEC.md, docs/DECISIONS.md, docs/DATA_REPORT.md, docs/EVAL_REPORT.md, docs/screens/. Local-only (gitignored): .env, data/, .venv, node_modules, .next, caches, .agents/, GEMINI.md, docs/TASKS.md, docs/ANTIGRAVITY_GUIDE.md, docs/SUBMISSION_MAP.md, docs/VIDEO_SCRIPT.md, master prompt, results JSON.
- Use the existing git user; never edit git config. NEVER `git push`; the human runs /ship.

## Token discipline (see .agents/rules/30-tokens.md)
- Search with `rg`/view ranges; do not open whole big files or data/.
- One task per conversation. Do not re-read files already summarised in the task.
- Keep prompts in prompts/*.md terse. LLM calls: cheap model for rewrite/ctx/tags (LLM_FAST_MODEL), cache results in data/cache/.
- Terminal output: pipe through `tail -n 30`.

## Layout
pathshala/ (api, pipeline, retrieval, db, llm, embed, text) · ingest/ · eval/ · mcp_server/ · web/ (Next.js) · prompts/ · db/schema.sql · scripts/ · tests/
Run: `make db` · `make api` · `make web` · `make verify` · `make eval`
