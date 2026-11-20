# PathShalaAI — System Architecture & Data Flow

## 1. End-to-End Architecture

```mermaid
flowchart TD
  subgraph Corpus["NCTB Datasets (CC BY 4.0)"]
    BN["Bangla Version (data/raw/mendeley)<br/>33 ingested books · Classes 1–5 · 7,081 chunks (bge-m3 + FTS)"]
    EN["English Version (data/raw/NCTB-SchoolText-English)<br/>79 ingested books · Classes 1–10 · 43,451 chunks (FTS + page ranges;<br/>1,093 bge-m3 vectors in Class 8 Science & Classes 1–2 Math)"]
  end

  subgraph DB["Neon PostgreSQL + pgvector"]
    TB["textbooks<br/>UNIQUE(curriculum_id, textbook_medium, class_level, subject)"]
    CH["chunks<br/>HNSW cosine + GIN simple FTS + page_start/page_end"]
    QR["queries & feedback<br/>PII-scrubbed, distress queries excluded"]
    LE["learning_events & session_mastery<br/>Idempotent event_key, EWMA per chapter"]
  end

  BN --> TB & CH
  EN --> TB & CH

  subgraph API["FastAPI Backend (pathshala/)"]
    SEC["Security Middleware<br/>RateLimiter, max body 3.2MB, X-Request-ID, TEACHER_TOKEN"]
    PIPE["LangGraph Tutor Pipeline (pipeline.py)<br/>Distress Gate (1098) -> Availability Check -> Rewrite -> Hybrid Retrieval -> Gate -> Answer -> clean_citations -> Verify"]
    CR["Concept Rescue (concept_rescue.py)<br/>Check MCQ -> Diagnose Likely Misconception -> Re-teach Simpler -> Fresh Practice"]
    MAST["Mastery Engine (mastery.py)<br/>Postgres EWMA persistence & session deletion"]
    MCP["nctb-corpus MCP Server (stdio)"]
  end

  subgraph Web["Next.js 16 Frontend (web/)"]
    SUI["/ Student Tutor & Concept Rescue UI<br/>Version / Class / Subject / Answer Language selectors"]
    TUI["/teacher Teacher Learning-Gap Dashboard<br/>Incorrect-rate heatmap, recurring misconceptions, privacy threshold"]
  end

  SUI --> SEC
  SEC --> PIPE --> CH
  PIPE -->|LiteLLM| GEM["Google Gemini API"]
  SUI --> CR --> CH
  CR -->|LiteLLM| GEM
  CR --> MAST --> LE
  TUI --> QR & LE
  MCP --> CH
```

## 2. Curriculum Identity & Version Isolation
- `curriculum_id` (`nctb`), `textbook_medium` (`bangla_version` | `english_version`), `class_level`, `subject`, and `answer_language` (`bn` | `en`) are independent concepts.
- Every SQL retrieval query applies exact predicates `WHERE t.curriculum_id = %(curr)s AND t.textbook_medium = %(med)s AND t.class_level = %(cl)s AND (%(subj)s IS NULL OR t.subject = %(subj)s)` before ranking.
- English Version chunk refs carry the `en-` prefix (`en-8-Science-3-4`) so Bangla Version (`8-Science-3-4`) and English Version chunks never collide.
- `clean_citations()` verifies every cited `chunk_id` was retrieved in the current request and matches `expected_medium`.

## 3. Concept Rescue State Flow
`ASK -> EXPLAIN (in chosen answer_language) -> CHECK (4-option grounded MCQ) -> DIAGNOSE (cautious likely misconception) -> RE-TEACH (simpler grounded explanation) -> PRACTICE (fresh MCQ on same learning objective) -> TRACK (idempotent EWMA update in PostgreSQL)`

## 4. Database Migrations & Rollback Guidance
- Migrations live in `db/migrations/` and are applied idempotently via `pathshala.db.apply_migrations()`:
  - `001_curriculum_identity.sql`: adds `curriculum_id`, `textbook_medium`, `edition_year`, `source_license` to `textbooks` and replaces `unique (class_level, subject)` with `unique (curriculum_id, textbook_medium, class_level, subject)`.
  - `002_concept_rescue_mastery.sql`: adds `learning_events` (with `unique (event_key)`) and `session_mastery`.
- **Rollback safety:** Because migrations are additive (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`), rollback can drop the new tables (`learning_events`, `session_mastery`) or restore a pre-migration Neon snapshot without touching existing `chunks` or `textbooks`.
