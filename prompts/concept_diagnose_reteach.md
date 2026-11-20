# Concept Rescue: Diagnose, Re-teach & Fresh Practice
A Class {class} student answered a diagnostic question incorrectly.
Using ONLY the untrusted textbook CONTEXT below, do 4 things in {answer_language}:
1. Acknowledge the attempt warmly without shaming ("feedback").
2. State the likely misconception cautiously based strictly on the chosen wrong option ("likely_misconception", starting with "{misc_prefix}", with "confidence" between 0.5 and 0.9). Never diagnose personal traits, intelligence, or mental health.
3. Give a simpler, alternative explanation or concrete everyday example grounded in CONTEXT ("reteach_explanation").
4. Write 1 brand-new 4-option MCQ testing the SAME learning objective ("follow_up") with a DIFFERENT question from PREVIOUS_QUESTION.
Return JSON only:
{"feedback": str, "likely_misconception": str, "confidence": float, "reteach_explanation": str, "follow_up": {"question_text": str, "options": [{"id": "A", "text": str}, {"id": "B", "text": str}, {"id": "C", "text": str}, {"id": "D", "text": str}], "correct_option": "A"|"B"|"C"|"D", "explanation": str, "misconception_labels": {"A": str, "B": str, "C": str, "D": str}}, "chunk_id": int}
