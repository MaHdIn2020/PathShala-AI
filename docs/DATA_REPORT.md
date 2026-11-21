# Data report

Measured with `ingest/mendeley.py` and verified across all 3 live Neon PostgreSQL shards.

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
| **Total on disk** | **58,872** | **132 books** | **43,341** | **79 books** |

## 3. Live 3-Shard PostgreSQL Inventory (Verified Full `BAAI/bge-m3` Coverage)

| Shard (`env`) | Scope | DB Size | Textbooks | Prepared Chunks | `bge-m3` Embedded (`1024-d`) | Chapter Page Ranges |
|---|---|---:|---:|---:|---:|---:|
| `DATABASE_URL` (Primary) | Bangla Version Classes 1–8 + operational/Concept Rescue tables | `496 MB` | `99` | `31,872` | `31,872` (100%) | `31,641` |
| `DATABASE_URL_BN_SSC` | Bangla Version Classes 9–10 (SSC) | `425 MB` | `33` | `27,141` | `27,141` (100%) | `27,141` |
| `DATABASE_URL_EN` | English Version Classes 1–10 | `640 MB` | `79` | `43,451` | `43,451` (100%) | `43,451` |
| **Total Across All Shards** | **NCTB Bangla + English Classes 1–10** | **`1,561 MB`** | **`211`** | **`102,464`** | **`102,464` (100%)** | **`102,233`** |

*Note:* `ingest/prepare.py` splits chunks exceeding `1500` chars into `-a`, `-b` segments (`58,872 -> 59,013` Bangla chunks; `43,341 -> 43,451` English chunks), matching the `132` Bangla books (`99` Classes 1–8 + `33` Classes 9–10) and `79` English books (`211` textbooks total).

## 4. Identity & Page Provenance Notes
- English Version chunk references are prefixed with `en-` (e.g., `en-8-Science-3-4`) so identical chapter/chunk indices never collide with Bangla Version chunks (`8-Science-3-4`).
- `chapters_config_<subject>.json` supplies chapter-level `start_page` and `end_page`. Where a subject lacks `chapters_config` (231 primary Bangla chunks), `page_start`/`page_end` remain `NULL` and the UI honestly reports chapter-level provenance without inventing page numbers.
- Source math/religion OCR contains occasional character noise (preserved verbatim without hallucination).
