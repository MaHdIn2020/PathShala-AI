# Data report

Measured with `ingest/mendeley.py` and verified against live PostgreSQL (`Neon AWS us-east-2`).

## 1. Sources & Attribution
- **NCTB Bangla Version (`data/raw/mendeley`):** Mendeley Data, DOI `10.17632/w3hj4m45d9.1`, CC BY 4.0 (*NCTB-PrimaryText / NCTB-SchoolText*).
- **NCTB English Version (`data/raw/NCTB-SchoolText-English`):** NCTB English Version textbook chunk corpus (`"lang": "en"`), CC BY 4.0, covering Classes 1–10.

## 2. On-Disk Corpus Inventory

| Class | Bangla Version Raw Chunks (`mendeley`) | Bangla Subjects | English Version Raw Chunks (`NCTB-SchoolText-English`) | English Subjects |
|---|---:|---:|---:|---:|
| Class 1 | 166 | 3 | 101 | 1 (`math`) |
| Class 2 | 279 | 3 | 168 | 1 (`math`) |
| Class 3 | 1,709 | 9 | 1,919 | 7 |
| Class 4 | 2,255 | 9 | 2,365 | 7 |
| Class 5 | 2,665 | 9 | 2,804 | 7 |
| Class 6 | 7,005 | 22 | 5,753 | 13 |
| Class 7 | 8,377 | 22 | 6,504 | 13 |
| Class 8 | 9,357 | 22 | 6,812 | 13 (`science`: 822 raw / 824 split) |
| Class 9–10 (`classNineTen`) | 27,059 | 33 | 16,915 | 17 |
| **Total on disk** | **58,872** | **134 books** | **43,341** | **79 books** |

## 3. Live PostgreSQL Inventory (Verified After Migration `001` & Ingestion)
- **Database Size:** `196 MB`
- **Bangla Version (`bangla_version`):** `33` textbooks (Classes 1–5), `7,081` chunks (`7,081` with `BAAI/bge-m3` 1024-d embeddings, `6,850` with chapter `page_start`–`page_end` mapped from `chapters_config_*.json`). Classes 6–10 Bangla Version are on disk and not yet ingested.
- **English Version (`english_version`):** `79` textbooks (Classes 1–10), `43,451` chunks (`43,451` indexed with Postgres `simple` GIN FTS + `100%` chapter `page_start`–`page_end`; `1,093` priority chunks embedded with `BAAI/bge-m3`: `824` in Class 8 Science + `269` in Classes 1–2 Math).
- **Total Indexed in DB:** `112` textbooks, `50,532` chunks (`8,174` dense vectors + `50,532` FTS rows).

## 4. Identity & Page Provenance Notes
- English Version chunk references are prefixed with `en-` (e.g., `en-8-Science-3-4`) so identical chapter/chunk indices never overwrite Bangla Version chunks (`8-Science-3-4`).
- `chapters_config_<subject>.json` supplies chapter-level `start_page` and `end_page` (e.g., Class 8 Science Ch. 3 `pp. 30–39`). Where a subject lacks `chapters_config`, `page_start`/`page_end` remain `NULL` and the UI honestly reports chapter-level provenance without inventing page numbers.
- Source math/religion OCR contains occasional character noise (preserved verbatim without hallucination).
