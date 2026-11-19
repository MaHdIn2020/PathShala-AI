# Error Analysis — Golden Set Failing Answerable Items

Source: `eval/results.json` joined with `eval/golden_set.jsonl`.
Total failing answerable items: **48** (out of 155 answerable).

## Breakdown by Category

| Category | Count | Share | Definition |
|---|---:|---:|---|
| `retrieval_miss` | 34 | 70.8% | Refused (`refused=True`): retrieval fell below `min_score` or verifier/model refused |
| `metric_artifact` | 9 | 18.8% | Answered with correct chapter citation (`cite_ok=True`) but Bangla paraphrase missed exact keyword recall |
| `generation_error` | 5 | 10.4% | Answered without matching gold chapter/chunk (`cite_ok=False`) |

## Breakdown by Subject

| Subject | Failing Count |
|---|---:|
| `english` | 11 |
| `christian_religion` | 9 |
| `math` | 8 |
| `bangla` | 5 |
| `bgs` | 5 |
| `science` | 4 |
| `hindu_religion` | 3 |
| `buddhist_religion` | 3 |

## Top Remediation Actions
1. **Retrieval misses (34/48):** Test `RERANK=1` (cross-encoder reranking) and contextualisation on weak subjects; lower refusal friction only where recall improves without hurting 32/32 off-syllabus refusal.
2. **Metric artifacts (9/48):** Add an LLM-judge scorer (`--judge` in `eval/run_eval.py`, using a different model than the answerer) alongside keyword recall so valid Bangla paraphrases are scored fairly.

## All 48 Failing Answerable Items

| ID | Class | Subject | Category | Refused | Cite OK | Question |
|---|---:|---|---|---|---|---|
| q_011 | 5 | `christian_religion` | `retrieval_miss` | True | False | পাঠ কত? |
| q_013 | 5 | `christian_religion` | `retrieval_miss` | True | False | চতুর্থ দিন বন্ধু কোথায় এসেছে? |
| q_014 | 5 | `christian_religion` | `metric_artifact` | False | True | বন্ধুর সুস্থ হয়ে আসার পর প্রথম অনুভূতি কী ছিল? |
| q_016 | 5 | `christian_religion` | `metric_artifact` | False | True | খ্রিস্টপ্রসাদ গ্রহণের ফলে আমরা কার সঙ্গে সংযুক্ত হই? |
| q_018 | 5 | `english` | `retrieval_miss` | True | False | What is the subject of class 5 mentioned in the passage? |
| q_019 | 5 | `english` | `retrieval_miss` | True | False | What is the name of the chapter in the passage? |
| q_020 | 5 | `english` | `retrieval_miss` | True | False | What is the activity number in 1.1 asking students to do in pairs? |
| q_025 | 5 | `english` | `retrieval_miss` | True | False | What are two main things asked in the exercise questions about Indonesia mentioned in the text? |
| q_027 | 5 | `hindu_religion` | `metric_artifact` | False | True | ভগবান বিষ্ণু কার পুত্ররূপে অবতীর্ণ হবেন বলে আশ্বাস দেন? |
| q_036 | 5 | `math` | `retrieval_miss` | True | False | কোন বিষয়ে শিক্ষার্থীদের প্রাপ্ত নম্বরের উপর ভিত্তি করে আয়তলেখ আঁকা হয়েছে? |
| q_038 | 5 | `science` | `retrieval_miss` | True | False | গ্রিনহাউস প্রভাব কাকে বলে? |
| q_041 | 5 | `science` | `retrieval_miss` | True | False | কোন মাধ্যমের সাহায্যে তথ্য প্রচারিত হলো? |
| q_046 | 5 | `science` | `retrieval_miss` | True | False | খেলতে গিয়ে মাটির উপর মার্বেল গড়িয়ে দিলে কিছু সময় পর কী ঘটে? |
| q_048 | 4 | `bangla` | `retrieval_miss` | True | False | স্বেণি কত? |
| q_049 | 4 | `bangla` | `retrieval_miss` | True | False | বিষয় কি? |
| q_051 | 4 | `bangla` | `retrieval_miss` | True | False | লিচু-চোর কুকুরের তাড়া খেয়ে কোথায় গেল? |
| q_052 | 4 | `bgs` | `retrieval_miss` | True | False | ১৪০_৩২_০৮: পাঠ্যপুস্তকের অধ্যায়টির নাম কআল? |
| q_053 | 4 | `buddhist_religion` | `generation_error` | False | False | শ্রেণি ও বিষয় কী? |
| q_054 | 4 | `buddhist_religion` | `metric_artifact` | False | True | দলগতভাবে কী উপস্থাপন করতে বলা হয়েছে? |
| q_058 | 4 | `christian_religion` | `generation_error` | False | False | যীশু শিষ্যদের কি বলেছিলেন? |
| q_060 | 4 | `christian_religion` | `retrieval_miss` | True | False | জলবায়ু পরিবর্তনের প্রভাবে কোনটির মান উন্নত হয়? |
| q_062 | 4 | `english` | `retrieval_miss` | True | False | What is the name of the chapter mentioned in the text? |
| q_068 | 4 | `hindu_religion` | `retrieval_miss` | True | False | নিজের দেশকে যিনি ভালোবাসেন, তাকে কী বলা হয়? |
| q_070 | 4 | `math` | `metric_artifact` | False | True | এই পাঠে কত সেমি বাহুবিশিষ্ট চতুর্ভুজ আঁকার কথা বলা হয়েছে? |
| q_071 | 4 | `math` | `generation_error` | False | False | এই পাঠটি কোন বিষয়ের অন্তর্গত? |
| q_072 | 4 | `math` | `retrieval_miss` | True | False | বর্গ এবং আয়তক্ষেত্রের কী নিয়ে আলোচনা করা হয়েছে? |
| q_080 | 1 | `math` | `metric_artifact` | False | True | ১৭ এবং ১৩ এর মধ্যে কোন সংখ্যাটি বেশি? |
| q_087 | 3 | `bangla` | `metric_artifact` | False | True | ব্যাঙ কোথায় বেড়াতে গিয়েছিল? |
| q_097 | 3 | `english` | `retrieval_miss` | True | False | What is the title of the chapter mentioned in the passage? |
| q_098 | 3 | `english` | `retrieval_miss` | True | False | What is the name of the rhyme in the passage? |
| q_102 | 3 | `math` | `retrieval_miss` | True | False | ১২৯৯৯ থেকে ১ বেশি সংখ্যাটি কত? |
| q_104 | 3 | `math` | `retrieval_miss` | True | False | ১০০০০ থেকে ১০ কম সংখ্যাটি কত? |
| q_105 | 3 | `math` | `retrieval_miss` | True | False | জাহিদের গণিতের বাড়ির কাজ শেষ করতে কত সময় লাগে? |
| q_107 | 3 | `science` | `retrieval_miss` | True | False | কতটি অধ্যায়ের বিষয় প্রাণী পরিচিতি? |
| q_108 | 2 | `english` | `generation_error` | False | False | What is the class mentioned in the passage? |
| q_109 | 2 | `english` | `retrieval_miss` | True | False | What is the subject of the chapter? |
| q_110 | 2 | `english` | `retrieval_miss` | True | False | What is the title of the chapter? |
| q_113 | 5 | `bangla` | `retrieval_miss` | True | False | প্রথম লাইনে কোন সংখ্যাটি বারবার এসেছে? |
| q_117 | 5 | `bgs` | `retrieval_miss` | True | False | প্লাস্টিক ও পলিথিন জাতীয় দ্রব্য সম্পর্কে কী বলা হয়েছে? |
| q_118 | 5 | `bgs` | `retrieval_miss` | True | False | জলবায়ু পরিবর্তন রোধে কোন বিষয়ে ভূমিকা পালন করতে বলা হয়েছে? |
| q_126 | 5 | `bgs` | `retrieval_miss` | True | False | মানুষ হিসেবে তাদের কোন অধিকার আছে? |
| q_127 | 5 | `bgs` | `retrieval_miss` | True | False | তারা কীভাবে চলাচল করতে পারেন? |
| q_128 | 5 | `buddhist_religion` | `generation_error` | False | False | সিদ্ধার্থ কীভাবে বুদ্ধত্ব লাভ করেন? |
| q_134 | 5 | `christian_religion` | `retrieval_miss` | True | False | খ্রীষ্টবিশ্বাসের মৌলিক শিক্ষাগুলোর মধ্যে কোনগুলো অন্যতম? |
| q_137 | 5 | `christian_religion` | `retrieval_miss` | True | False | যীশু খ্রীষ্ট সম্পর্কে আমরা কী ধারণা লাভ করি? |
| q_140 | 5 | `christian_religion` | `metric_artifact` | False | True | দীক্ষাস্নানের মাধ্যমে আমরা কোথায় প্রবেশ করি? |
| q_145 | 5 | `english` | `retrieval_miss` | True | False | What tools are used for working in the school garden? |
| q_155 | 5 | `hindu_religion` | `metric_artifact` | False | True | কর্মযোগে সিদ্ধ পুরুষ কী লাভ করেন? |
