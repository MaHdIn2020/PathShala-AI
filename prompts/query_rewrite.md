# P5 query rewriter v2
Rewrite the student's question into one clear standalone {target_lang} search query matching NCTB textbook terminology. Add likely textbook terms in {target_lang}. Do not answer it.
Return JSON only: {"query": str, "subject_guess": str, "keywords": [str]}.
