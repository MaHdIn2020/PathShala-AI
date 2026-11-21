# PathShalaAI — System Architecture & Data Flow

## 1. End-to-End 3-Shard Architecture

```mermaid
flowchart TD
  subgraph Corpus["NCTB Datasets (CC BY 4.0) — Full RTX 4060 bge-m3 (1024-d)"]
    BN18["Bangla Version Classes 1–8<br/>99 books · 31,872 embedded chunks"]
    BN910["Bangla Version Classes 9–10 (SSC)<br/>33 books · 27,141 embedded chunks"]
    EN["English Version Classes 1–10<br/>79 books · 43,451 embedded chunks"]
  end

  subgraph Shards["3-Database Neon PostgreSQL + pgvector Topology"]
    DB1["DATABASE_URL (Primary, 496 MB)<br/>Bangla 1–8 + queries, feedback, learning_events, session_mastery"]
    DB2["DATABASE_URL_BN_SSC (425 MB)<br/>Bangla 9–10 (SSC) textbooks & chunks"]
    DB3["DATABASE_URL_EN (640 MB)<br/>English Version 1–10 textbooks & chunks"]
  end

  BN18 --> DB1
  BN910 --> DB2
  EN --> DB3

  subgraph API["FastAPI Backend (pathshala/)"]
    SEC["Security Middleware<br/>RateLimiter, max body 3.2MB, X-Request-ID, TEACHER_TOKEN"]
    ROUTE["Shard Router (db.resolve_db_url)<br/>(textbook_medium, class_level) -> DB1 | DB2 | DB3"]
    PIPE["LangGraph Tutor Pipeline (pipeline.py)<br/>Distress Gate (1098) -> Availability Check -> Rewrite -> Hybrid Retrieval -> Gate -> Answer -> clean_citations -> Verify"]
    CR["Concept Rescue (concept_rescue.py)<br/>Check MCQ -> Diagnose Likely Misconception -> Re-teach Simpler -> Fresh Practice"]
    MAST["Mastery Engine (mastery.py)<br/>Postgres EWMA persistence & session deletion (DB1)"]
    MCP["nctb-corpus MCP Server (stdio)"]
  end

  subgraph Web["Next.js 16 Frontend (web/)"]
    SUI["/ Student Tutor & Concept Rescue UI<br/>Version / Class / Subject / Answer Language selectors"]
    TUI["/teacher Teacher Learning-Gap Dashboard<br/>Incorrect-rate heatmap, recurring misconceptions, privacy threshold"]
  end

  SUI --> SEC --> PIPE --> ROUTE --> DB1 & DB2 & DB3
  PIPE -->|LiteLLM| GEM["Google Gemini API"]
  SUI --> CR --> ROUTE
  CR -->|LiteLLM| GEM
  CR --> MAST --> DB1
  TUI --> DB1
  MCP --> ROUTE
```

## 2. 3-Database Shard Routing (`pathshala/db.py`)
- `resolve_db_url(textbook_medium, class_level, cfg)` routes every textbook read/write cleanly:
  - `("english_version", any class)` -> `DATABASE_URL_EN`
  - `("bangla_version", class >= 9)` -> `DATABASE_URL_BN_SSC`
  - `("bangla_version", class <= 8)` -> `DATABASE_URL` (Primary)
- Operational tables (`queries`, `feedback`, `eval_runs`, `learning_events`, `session_mastery`) always reside on the primary `DATABASE_URL`.
- When `DATABASE_URL_BN_SSC` and `DATABASE_URL_EN` are omitted or empty, `Config` automatically falls back to `DATABASE_URL` for seamless local single-DB development.
- `get_curriculum_catalog()` and `/health/ready` query all configured shards and merge books deterministically via `merge_shard_books()`, preferring the authoritative shard for each `(curriculum_id, textbook_medium, class_level, subject)`.

## 3. Curriculum Identity & Version Isolation
- `curriculum_id` (`nctb`), `textbook_medium` (`bangla_version` | `english_version`), `class_level`, `subject`, and `answer_language` (`bn` | `en`) are independent concepts.
- Every SQL retrieval query applies exact predicates `WHERE t.curriculum_id = %(curr)s AND t.textbook_medium = %(med)s AND t.class_level = %(cl)s AND (%(subj)s IS NULL OR t.subject = %(subj)s)` before ranking.
- English Version chunk refs carry the `en-` prefix (`en-8-Science-3-4`) so Bangla Version (`8-Science-3-4`) and English Version chunks never collide.
- `clean_citations()` verifies every cited `chunk_id` was retrieved in the current request and matches `expected_medium`.

## 4. Concept Rescue State Flow
`ASK -> EXPLAIN (in chosen answer_language) -> CHECK (4-option grounded MCQ) -> DIAGNOSE (cautious likely misconception) -> RE-TEACH (simpler grounded explanation) -> PRACTICE (fresh MCQ on same learning objective) -> TRACK (idempotent EWMA update in PostgreSQL)`

## 5. Database Migrations & Rollback Guidance
- Migrations live in `db/migrations/` and are applied idempotently across all unique shards via `pathshala.db.apply_migrations()`:
  - `schema.sql`: base extensions (`vector`), tables, HNSW vector index, and GIN `simple` FTS index.
  - `001_curriculum_identity.sql`: adds `curriculum_id`, `textbook_medium`, `edition_year`, `source_license` to `textbooks` and replaces `unique (class_level, subject)` with `unique (curriculum_id, textbook_medium, class_level, subject)`.
  - `002_concept_rescue_mastery.sql`: adds `learning_events` (with `unique (event_key)`) and `session_mastery`.
- **Rollback safety:** Because migrations are additive (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`), rollback can drop the new tables (`learning_events`, `session_mastery`) or restore a pre-migration Neon snapshot without touching existing `chunks` or `textbooks`.
