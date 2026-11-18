# Data report

Measured with `python scripts/inspect_dataset.py data/raw/mendeley` (loader: `ingest/mendeley.py`).

## Source
Mendeley Data, DOI 10.17632/w3hj4m45d9.1, CC BY 4.0. The bundled README names it **NCTB-SchoolText**: classes 1-10, not primary only.

## Shape
- 1,535 `.jsonl` files, one per chapter: `class*/processed_chapters_<subject>/class<N>_<Subject>_ch<K>.jsonl`.
- 132 `chapters_config_<subject>.json` files with chapter title and `start_page`/`end_page`. The loader skips them because they have no `text`.
- JSONL fields: `class`, `subject`, `chapter_no`, `chapter_title`, `chunk_id`, `text`.
- `chunk_id` form: `<class>-<Subject>-<chapter_no>-<chunk_index>`.
- Chunk records carry no page numbers, so citations use class, subject, chapter and chunk id.
- The loader reads all of it as-is. Usable records: 58,872, equal to the README's chunk count. 1,535 chapters, 34 subjects.

## Chunks by class (loader output)
| class | chunks |
|---|---|
| 1 | 166 |
| 2 | 279 |
| 3 | 1,709 |
| 4 | 2,255 |
| 5 | 2,665 |
| 6 | 7,005 |
| 7 | 8,377 |
| 8 | 9,357 |
| 9 (the combined 9-10 SSC set) | 27,059 |

Classes 1-5 total 7,074 chunks.

## Chunk length (chars, all classes)
min 1 · median 351 · p95 701 · max 2,968.

## Noise
- Math OCR is noisy, for example `গাণিতিক বাক্য ৪৬১৪ ৩৬৫ - [|` and stray `*`, `[:`.
- Some chunks are very short, such as a chapter heading only (`প্রথম অধ্যায়` plus the title).

## Notes
- Class `"9-10"` is read as 9 because `to_int` takes the first number.
- Classes 6-10 are in the data but out of the project scope (primary 1-5). Ingest filtering is a T04/T07 decision.
- Attribution: CC BY 4.0, keep in README.
