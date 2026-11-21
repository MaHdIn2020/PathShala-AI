# Evaluation Report — PathShala AI

## 1. Historical Baseline (`eval/golden_set.jsonl`, `n = 187`, Classes 1–5 Bangla Version)
Measured from [eval/results.json](../eval/results.json) (RAG) and [eval/results_baseline.json](../eval/results_baseline.json) (plain LLM baseline, no retrieval) on [eval/golden_set.jsonl](../eval/golden_set.jsonl).

![RAG vs Baseline Evaluation Chart](eval_chart.png)

### Method & Dataset (v1)
- **Golden set (`n = 187`):** `155` answerable questions across NCTB primary textbooks (Classes 1–5 Bangla Version) + `32` off-syllabus questions (`answerable: false`).
- **Metrics (`eval/run_eval.py`):**
  - `answer_accuracy`: fraction of answerable items not refused and achieving strict substring `keyword_recall >= 0.5`.
  - `citation_correctness`: fraction of answerable items not refused whose rebuilt citations include a `gold_chapters` or `gold_refs` match.
  - `refusal_accuracy`: fraction of off-syllabus items properly refused (`refused == true`).

### Measured Results (v1 Baseline — Historical)

| Metric | RAG (`PathShala AI`) | Baseline (`Plain LLM`) | Delta |
|---|---:|---:|---:|
| Sample size (`n`) | 187 | 187 | — |
| **Answer Accuracy** (155 answerable) | **69.0%** (`107/155`) | 13.5% (`21/155`) | +55.5 pts |
| **Citation Correctness** (155 answerable) | **71.6%** (`111/155`) | 0.0% | +71.6 pts |
| **Refusal Accuracy** (32 off-syllabus) | **100.0%** (`32/32`) | 37.5% (`12/32`) | +62.5 pts |
| p95 Latency (ms) | 13,649 ms | 2,693 ms | +10,956 ms |
| Mean Cost / Query (USD) | \$0.00078 | \$0.00006 | +\$0.00072 |

- Among the `155` answerable questions, RAG refused `34` (`21.9%`) and answered `121` (`78.1%`).
- Every off-syllabus question (`32/32`) was refused by RAG (`100.0%` refusal accuracy).

---

## 2. Versioned Multi-Curriculum Benchmark (`eval/golden_set_v2.jsonl`, `n = 205`)
Added in Phase 6 without overwriting the v1 baseline:
- **Composition (`n = 205`):**
  - `187` v1 Bangla Version rows (`curriculum_id="nctb"`, `textbook_medium="bangla_version"`, `answer_language="bn"`).
  - `18` manually authored & chunk-verified rows (`q_188`–`q_205`) covering:
    - NCTB English Version Class 8 Science (`en-8-Science-3-4`, `en-8-Science-6-2`, `en-8-Science-6-4`, `en-8-Science-10-4`) with both English (`en`) and Bangla (`bn`) explanation targets.
    - Banglish / code-switched queries (`q_195`, `q_200`).
    - Classes 1, 3, and 5 English Version (`en-1-Math-1-1`, `en-3-Science-7-4`, `en-5-Science-1-4`).
    - Cross-version & unavailable curriculum refusals (`q_201`–`q_205`, e.g., Class 1 Science English Version and Class 8 Science Bangla Version).
- **New Metric Definitions in `eval/run_eval.py`:**
  - `answerable_false_refusal_rate`: share of answerable items incorrectly refused.
  - `refusal_precision`: `TP_refusal / (TP_refusal + FP_refusal)`.
  - `curriculum_version_leakage_count`: number of responses citing a `textbook_medium` or `class_level` different from the item's requested metadata.
  - `p50_latency_ms` & `p95_latency_ms`, plus `error_rate`.
- **Execution Note:** Full live LLM run over all 205 v2 items requires a running API server and Gemini quota (`python -m eval.run_eval --api http://localhost:8000 --golden eval/golden_set_v2.jsonl --out eval/results_v2.json`); do not claim v2 LLM accuracy percentages until executed end-to-end.

## 3. Known Limitations
- **Keyword recall is strict:** Substring matching (`keyword_recall >= 0.5`) penalizes valid Bangla paraphrases (use `--judge` for semantic grading).
- **Full hybrid vector coverage achieved across all 211 textbooks:** All `102,464` chunks across Bangla Version Classes 1–10 and English Version Classes 1–10 now carry `BAAI/bge-m3` (`1024-d`) embeddings alongside Postgres `simple` FTS.
- **OCR noise in source corpus:** Some Math and Religion chunks contain OCR artifacts.
