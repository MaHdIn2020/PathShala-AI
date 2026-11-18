# P7 eval Q&A generator v1
From PASSAGE write up to 3 question-answer pairs a student might ask. Each answer must be directly extractable from PASSAGE.
Return JSON only: {"items": [{"question": str, "keywords": [str]}]}. keywords = 2-4 short answer terms that must appear in a correct answer.
