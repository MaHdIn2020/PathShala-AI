# P2 verifier v1
Given ANSWER and CONTEXT, list each factual claim in ANSWER. For each: supported or unsupported, plus the supporting chunk_id.
Return JSON only: {"verdict": "PASS"|"FAIL", "unsupported": [str]}. verdict=FAIL if any claim is unsupported.
