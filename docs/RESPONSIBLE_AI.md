# PathShalaAI — Responsible AI, Child Safety & Provider Data-Flow Disclosure

## 1. Model & Corpus Overview
- **Intended Use:** Curriculum-grounded tutoring and Concept Rescue diagnosis for Bangladeshi school students using NCTB Bangla Version and NCTB English Version textbooks, plus anonymous aggregate topic/misconception insights for teachers.
- **Out-of-Scope Use:** Clinical/mental-health diagnosis, medical prescribing, political persuasion, ungrounded general chat, or tracking individual students' private conversations.
- **Corpus & Attribution:**
  - Bangla Version (`data/raw/mendeley`): 7,081 indexed chunks across 33 primary textbooks (Classes 1–5), all with `BAAI/bge-m3` embeddings (6,850 with chapter page ranges).
  - English Version (`data/raw/NCTB-SchoolText-English`): 43,451 indexed chunks across 79 textbooks (Classes 1–10), all with chapter page ranges (`page_start`–`page_end`), plus `BAAI/bge-m3` embeddings on priority textbooks (Class 8 Science: 824 chunks; Classes 1–2 Math: 269 chunks).
  - Source licence: CC BY 4.0 (Mendeley NCTB-PrimaryText / NCTB-SchoolText).

## 2. External Provider & Data-Flow Transparency
| Component | Provider / Location | Data Sent Externally | Retention & Privacy Posture |
|---|---|---|---|
| **Question Embedding & Retrieval** | Local `BAAI/bge-m3` (1024-d) + PostgreSQL (`pgvector` HNSW + `simple` GIN FTS) | None for local `bge-m3`; search queries executed against managed PostgreSQL | Query embedding happens locally in API process |
| **PostgreSQL Database** | Neon managed PostgreSQL (`AWS us-east-2`) | Textbook chunks, PII-scrubbed query logs, anonymous `session_id` learning events & EWMA mastery | Student accounts not required; `DELETE /session/{session_id}` erases session history |
| **LLM Generation, Query Rewrite & Verification** | Google Gemini via LiteLLM (`gemini-3-flash-preview`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`) | Student question (trimmed to `max_question_chars=600`), selected textbook chunks in `CONTEXT`, diagnostic MCQ options | Governed by configured Google Gemini API plan; PathShalaAI does **not** claim Bangladesh-only data residency or contractual zero-retention without signed enterprise agreements |
| **Textbook Photo OCR (`/ask-image`)** | Google Gemini multimodal API via LiteLLM | Base64 image (capped at 2 MB) during the single OCR request | Images are processed strictly in memory and **never** saved to disk, object storage, or database |

## 3. Child Safety & Privacy Mitigations
| Risk | Mitigation | Verification |
|---|---|---|
| **Child in emotional distress** | Deterministic pre-retrieval `is_distress_query()` gate covers Bangla, English, and Banglish phrasing; immediately returns calm encouragement to contact a trusted adult + verified Child Helpline **1098** without calling the LLM | `tests/test_pipeline.py`, `tests/test_math_and_norm.py`, `scripts/redteam.py` |
| **Distress privacy leakage** | Queries flagged `safety_distress` are **never logged** to the `queries` table and never enter teacher analytics | `pathshala/db.py:log_query`, `pathshala/api.py`, `tests/test_security.py` |
| **PII exposure in analytics** | `scrub_pii()` strips BD mobile numbers, email addresses, and explicit self-reported names before storing any query string | `pathshala/security.py`, `tests/test_security.py` |
| **Small-cohort identification in teacher dashboard** | Real-student Concept Rescue aggregates with fewer than `min_group_size=3` distinct sessions are suppressed from teacher summaries | `pathshala/db.py`, `tests/test_teacher_summary.py` |
| **Prompt injection in text, OCR, or retrieved chunks** | System prompts mark `CONTEXT` and `QUESTION` as untrusted data; `clean_citations()` strips any `chunk_id` not returned by SQL retrieval or belonging to a different `textbook_medium` | `tests/test_curriculum_isolation.py`, `tests/test_pipeline.py` |
| **Psychological labeling of minors** | Misconception diagnosis uses cautious wording (`Likely misconception:` / `সম্ভাব্য ভুল ধারণা:`) tied strictly to the current concept; EWMA mastery is labeled `estimated_practice_mastery` | `pathshala/concept_rescue.py`, `pathshala/mastery.py`, `tests/test_concept_rescue.py` |

## 4. Red-Team Verification (`scripts/redteam.py`)
Executed **50** adversarial prompts across Bangla/English/Banglish distress (`1098`), jailbreaks, prompt injections, adult/unsafe, politics, medical prescribing, and Class 6+ / off-syllabus boundaries (`PYTHONPATH=. python scripts/redteam.py`).
