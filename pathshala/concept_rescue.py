"""Concept Rescue learning loop: CHECK -> DIAGNOSE -> RE-TEACH -> PRACTICE -> TRACK.
All questions, diagnoses, and re-teaching stay strictly grounded within the selected curriculum & textbook_medium."""
import hashlib

from . import mastery
from .config import get_config
from .pipeline import clean_citations, format_context, load_prompt, subject_min_score
from .text import normalize_bangla

_OPTION_IDS = ("A", "B", "C", "D")


def _misc_prefix(answer_language: str) -> str:
    return "Likely misconception:" if answer_language == "en" else "সম্ভাব্য ভুল ধারণা:"


def _cautious_label(raw: str | None, answer_language: str, fallback: str | None = None) -> str:
    prefix = _misc_prefix(answer_language)
    txt = (raw or fallback or "").strip()
    if not txt:
        txt = (
            "The selected option confuses a key textbook relationship."
            if answer_language == "en"
            else "নির্বাচিত উত্তরটি পাঠ্যবইয়ের মূল ধারণার সাথে বিভ্রান্তি নির্দেশ করে।"
        )
    low = txt.lower()
    if "likely misconception" not in low and "সম্ভাব্য ভুল ধারণা" not in txt:
        txt = f"{prefix} {txt}"
    return txt


def _norm_options(raw_opts) -> list[dict] | None:
    if not isinstance(raw_opts, list) or len(raw_opts) != 4:
        return None
    out = []
    seen = set()
    for idx, item in enumerate(raw_opts):
        if isinstance(item, dict):
            oid = str(item.get("id") or _OPTION_IDS[idx]).strip().upper()
            text = str(item.get("text") or "").strip()
        else:
            oid = _OPTION_IDS[idx]
            text = str(item or "").strip()
        if oid not in _OPTION_IDS or oid in seen or not text:
            return None
        seen.add(oid)
        out.append({"id": oid, "text": text})
    return out if len(out) == 4 else None


def _qid(seed_text: str) -> str:
    return "cr-" + hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:10]


def _resolve_chunks(
    query: str,
    class_level: int,
    subject: str | None,
    curriculum_id: str,
    textbook_medium: str,
    chunk_id: int | None,
    cfg,
    retrieve_fn,
) -> list[dict]:
    chunks = []
    if retrieve_fn is not None:
        try:
            chunks = retrieve_fn(
                query,
                class_level,
                subject,
                cfg,
                curriculum_id=curriculum_id,
                textbook_medium=textbook_medium,
            )
        except TypeError:
            chunks = retrieve_fn(query, class_level, subject, cfg)
    else:
        from . import db, retrieval

        if chunk_id is not None:
            one = db.get_chunk(chunk_id, textbook_medium=textbook_medium, class_level=class_level)
            if one and one.get("textbook_medium") == textbook_medium and int(one.get("class_level") or 0) == int(class_level):
                chunks.append({**one, "sim": 0.9})
        found = retrieval.search(
            query,
            class_level,
            subject,
            cfg=cfg,
            curriculum_id=curriculum_id,
            textbook_medium=textbook_medium,
        )
        seen = {c["id"] for c in chunks}
        for c in found:
            if c["id"] not in seen:
                chunks.append(c)
                seen.add(c["id"])
    return [c for c in chunks if not c.get("textbook_medium") or c.get("textbook_medium") == textbook_medium]


def _validate_mcq_payload(
    obj: dict,
    chunks: list[dict],
    textbook_medium: str,
    answer_language: str,
    exclude_questions: list[str] | None = None,
) -> tuple[dict | None, dict | None]:
    if not isinstance(obj, dict):
        return None, None
    q_text = str(obj.get("question_text") or "").strip()
    opts = _norm_options(obj.get("options"))
    correct_opt = str(obj.get("correct_option") or "").strip().upper()
    if not q_text or not opts or correct_opt not in _OPTION_IDS:
        return None, None
    if exclude_questions:
        norm_q = q_text.lower()
        if any(norm_q == str(ex or "").strip().lower() for ex in exclude_questions):
            return None, None

    raw_cid = obj.get("chunk_id")
    cites = clean_citations([{"chunk_id": raw_cid}], chunks, expected_medium=textbook_medium)
    if not cites:
        cites = clean_citations([{"chunk_id": chunks[0]["id"]}], chunks, expected_medium=textbook_medium) if chunks else []
    if not cites:
        return None, None
    cite = cites[0]

    raw_misc = obj.get("misconception_labels") if isinstance(obj.get("misconception_labels"), dict) else {}
    misc_labels = {}
    for o in opts:
        oid = o["id"]
        if oid == correct_opt:
            continue
        misc_labels[oid] = _cautious_label(raw_misc.get(oid), answer_language)

    item = {
        "question_text": q_text,
        "options": opts,
        "correct_option": correct_opt,
        "explanation": str(obj.get("explanation") or "").strip(),
        "misconception_labels": misc_labels,
    }
    return item, cite


def generate_diagnostic_check(
    question: str,
    answer: str,
    class_level: int,
    subject: str | None = None,
    *,
    curriculum_id: str = "nctb",
    textbook_medium: str = "bangla_version",
    answer_language: str = "bn",
    chunk_id: int | None = None,
    learning_objective: str | None = None,
    exclude_questions: list[str] | None = None,
    cfg=None,
    retrieve_fn=None,
    llm_fn=None,
) -> dict:
    """Generate 1 grounded diagnostic MCQ with cautious distractor misconception labels."""
    cfg = cfg or get_config()
    curr = (curriculum_id or "nctb").strip().lower()
    med = (textbook_medium or "bangla_version").strip().lower()
    ans_lang = "en" if str(answer_language or "bn").strip().lower() == "en" else "bn"
    q_clean = normalize_bangla(question)[: cfg.max_question_chars]

    if not q_clean:
        return {"refused": True, "reason": "empty_question", "message": "প্রশ্ন খালি রাখা যাবে না।", "cost_usd": 0.0}

    chunks = _resolve_chunks(q_clean, class_level, subject, curr, med, chunk_id, cfg, retrieve_fn)
    top = max((c.get("sim", 0.0) for c in chunks), default=0.0)
    if not chunks or (chunk_id is None and top < subject_min_score(subject, cfg.min_score)):
        msg = (
            "No verified textbook evidence found for a diagnostic check."
            if ans_lang == "en"
            else "এই বিষয়ে যাচাই প্রশ্ন তৈরির জন্য পাঠ্যবইয়ে পর্যাপ্ত প্রমাণ পাওয়া যায়নি।"
        )
        return {"refused": True, "reason": "low_retrieval", "message": msg, "cost_usd": 0.0}

    if llm_fn is None:
        from . import llm

        llm_fn = llm.chat_json

    lang_label = "English" if ans_lang == "en" else "Bangla (বাংলা)"
    sys_prompt = (
        load_prompt("concept_check")
        .replace("{class}", str(class_level))
        .replace("{answer_language}", lang_label)
        .replace("{misc_prefix}", _misc_prefix(ans_lang))
    )
    ctx = format_context(chunks, cfg.max_context_chars)
    user_msg = f"CONTEXT:\n{ctx}\n\nSTUDENT_QUESTION: {q_clean}\nEXPLANATION_GIVEN: {(answer or '')[:600]}"
    if learning_objective:
        user_msg += f"\nLEARNING_OBJECTIVE: {learning_objective}"
    if exclude_questions:
        user_msg += "\nAVOID_REPEATING: " + " | ".join(str(x)[:120] for x in exclude_questions[:3])

    cost = 0.0
    try:
        obj, u = llm_fn(sys_prompt, user_msg, cfg.llm_model, 2048)
        cost += u.get("cost", 0.0)
        if not obj:
            obj, u2 = llm_fn(sys_prompt, user_msg, cfg.llm_fast_model, 2048)
            cost += u2.get("cost", 0.0)
    except Exception:
        obj = {}

    item, cite = _validate_mcq_payload(obj, chunks, med, ans_lang, exclude_questions=exclude_questions)
    if not item or not cite:
        msg = (
            "Could not build a grounded diagnostic check right now. Please try again."
            if ans_lang == "en"
            else "এই মুহূর্তে পাঠ্যবই-ভিত্তিক যাচাই প্রশ্ন তৈরি করা যায়নি। আবার চেষ্টা করো।"
        )
        return {"refused": True, "reason": "ungrounded_diagnostic", "message": msg, "cost_usd": cost}

    obj_txt = str(obj.get("learning_objective") or learning_objective or cite.get("chapter") or q_clean[:80]).strip()
    qid = _qid(f"{curr}|{med}|{cite.get('chunk_ref')}|{item['question_text']}")
    return {
        "refused": False,
        "reason": None,
        "question_id": qid,
        "curriculum_id": curr,
        "textbook_medium": med,
        "class_level": cite.get("class_level") or class_level,
        "subject": cite.get("subject") or subject or "general",
        "chapter_no": cite.get("chapter_no"),
        "chapter": cite.get("chapter") or "অধ্যায়",
        "learning_objective": obj_txt,
        "question_text": item["question_text"],
        "answer_language": ans_lang,
        "question_type": "mcq",
        "options": item["options"],
        "correct_option": item["correct_option"],
        "explanation": item["explanation"],
        "misconception_labels": item["misconception_labels"],
        "source": cite,
        "cost_usd": cost,
    }


def submit_diagnostic_answer(
    session_id: str,
    diagnostic: dict,
    selected_option: str,
    *,
    event_key: str | None = None,
    answer_language: str | None = None,
    use_db: bool = False,
    cfg=None,
    retrieve_fn=None,
    llm_fn=None,
) -> dict:
    """Evaluate student's diagnostic response, diagnose likely misconception, re-teach & generate fresh practice."""
    cfg = cfg or get_config()
    sel = str(selected_option or "").strip().upper()
    if sel not in _OPTION_IDS:
        raise ValueError("selected_option must be A, B, C, or D")

    ans_lang = "en" if str(answer_language or diagnostic.get("answer_language") or "bn").strip().lower() == "en" else "bn"
    correct_opt = str(diagnostic.get("correct_option") or "").strip().upper()
    is_correct = sel == correct_opt

    source = diagnostic.get("source") or {}
    curr = (diagnostic.get("curriculum_id") or source.get("curriculum_id") or "nctb").strip().lower()
    med = (diagnostic.get("textbook_medium") or source.get("textbook_medium") or "bangla_version").strip().lower()
    cls = int(diagnostic.get("class_level") or source.get("class_level") or 5)
    subj = diagnostic.get("subject") or source.get("subject") or "general"
    chap = diagnostic.get("chapter") or source.get("chapter") or "অধ্যায়"
    obj_txt = diagnostic.get("learning_objective") or chap

    raw_misc = None if is_correct else _cautious_label(
        (diagnostic.get("misconception_labels") or {}).get(sel),
        ans_lang,
    )

    attempt = mastery.record_attempt(
        session_id,
        cls,
        subj,
        chap,
        is_correct,
        curriculum_id=curr,
        textbook_medium=med,
        event_key=event_key,
        learning_objective=obj_txt,
        event_type="concept_rescue_check",
        question_id=diagnostic.get("question_id"),
        selected_option=sel,
        likely_misconception=raw_misc,
        use_db=use_db,
    )
    snap = mastery.get_session_mastery(session_id, use_db=use_db)

    if is_correct:
        fb = (
            f"Great job! Option {correct_opt} is correct. {diagnostic.get('explanation') or ''}".strip()
            if ans_lang == "en"
            else f"চমৎকার! {correct_opt} উত্তরটি সঠিক। {diagnostic.get('explanation') or ''}".strip()
        )
        return {
            "is_correct": True,
            "selected_option": sel,
            "correct_option": correct_opt,
            "feedback": fb,
            "likely_misconception": None,
            "confidence": None,
            "reteach_explanation": None,
            "follow_up_question": None,
            "source": source,
            "attempt": attempt,
            "mastery": snap,
            "cost_usd": 0.0,
        }

    # Wrong answer path: retrieve same-version chunk, diagnose cautiously, re-teach simpler, generate fresh MCQ
    chunks = _resolve_chunks(
        f"{chap} {obj_txt}",
        cls,
        subj if subj != "general" else None,
        curr,
        med,
        source.get("chunk_id"),
        cfg,
        retrieve_fn,
    )
    if not chunks and source.get("chunk_id") and source.get("snippet"):
        chunks = [
            {
                "id": source["chunk_id"],
                "chunk_ref": source.get("chunk_ref"),
                "book": source.get("book"),
                "curriculum_id": curr,
                "textbook_medium": med,
                "class_level": cls,
                "subject": subj,
                "chapter_no": source.get("chapter_no"),
                "chapter": chap,
                "page_start": source.get("page_start"),
                "page_end": source.get("page_end"),
                "text": source.get("snippet") or "",
                "sim": 0.8,
            }
        ]

    if llm_fn is None:
        from . import llm

        llm_fn = llm.chat_json

    lang_label = "English" if ans_lang == "en" else "Bangla (বাংলা)"
    sys_prompt = (
        load_prompt("concept_diagnose_reteach")
        .replace("{class}", str(cls))
        .replace("{answer_language}", lang_label)
        .replace("{misc_prefix}", _misc_prefix(ans_lang))
    )
    ctx = format_context(chunks, cfg.max_context_chars)
    user_msg = (
        f"CONTEXT:\n{ctx}\n\n"
        f"LEARNING_OBJECTIVE: {obj_txt}\n"
        f"PREVIOUS_QUESTION: {diagnostic.get('question_text')}\n"
        f"OPTIONS: {diagnostic.get('options')}\n"
        f"CORRECT_OPTION: {correct_opt}\n"
        f"STUDENT_SELECTED_OPTION: {sel}\n"
        f"DISTRACTOR_HINT: {raw_misc}"
    )

    cost = 0.0
    parsed = {}
    if chunks:
        try:
            parsed, u = llm_fn(sys_prompt, user_msg, cfg.llm_model, 2400)
            cost += u.get("cost", 0.0)
            if not parsed:
                parsed, u2 = llm_fn(sys_prompt, user_msg, cfg.llm_fast_model, 2400)
                cost += u2.get("cost", 0.0)
        except Exception:
            parsed = {}

    feedback = str(parsed.get("feedback") or "").strip() or (
        "Good try! Let's look at this concept from a simpler angle."
        if ans_lang == "en"
        else "চেষ্টা করার জন্য ধন্যবাদ! চলো বিষয়টি আরও সহজভাবে আরেকবার দেখি।"
    )
    likely_misc = _cautious_label(parsed.get("likely_misconception"), ans_lang, fallback=raw_misc)
    try:
        conf = max(0.35, min(0.95, float(parsed.get("confidence") or 0.72)))
    except Exception:
        conf = 0.72

    reteach = str(parsed.get("reteach_explanation") or "").strip() or str(diagnostic.get("explanation") or "").strip()
    if not reteach:
        reteach = (
            "Please review the cited textbook excerpt above for the core definition."
            if ans_lang == "en"
            else "উপরে উল্লেখিত পাঠ্যবইয়ের অংশটি আরেকবার মন দিয়ে পড়ো।"
        )

    fu_raw = parsed.get("follow_up") if isinstance(parsed.get("follow_up"), dict) else {}
    if fu_raw and "chunk_id" not in fu_raw and parsed.get("chunk_id") is not None:
        fu_raw = {**fu_raw, "chunk_id": parsed.get("chunk_id")}
    fu_item, fu_cite = _validate_mcq_payload(
        fu_raw,
        chunks,
        med,
        ans_lang,
        exclude_questions=[diagnostic.get("question_text") or ""],
    )

    follow_up_question = None
    if fu_item and fu_cite:
        fu_qid = _qid(f"{curr}|{med}|{fu_cite.get('chunk_ref')}|{fu_item['question_text']}")
        follow_up_question = {
            "question_id": fu_qid,
            "curriculum_id": curr,
            "textbook_medium": med,
            "class_level": fu_cite.get("class_level") or cls,
            "subject": fu_cite.get("subject") or subj,
            "chapter_no": fu_cite.get("chapter_no"),
            "chapter": fu_cite.get("chapter") or chap,
            "learning_objective": obj_txt,
            "question_text": fu_item["question_text"],
            "answer_language": ans_lang,
            "question_type": "mcq",
            "options": fu_item["options"],
            "correct_option": fu_item["correct_option"],
            "explanation": fu_item["explanation"],
            "misconception_labels": fu_item["misconception_labels"],
            "source": fu_cite,
        }

    return {
        "is_correct": False,
        "selected_option": sel,
        "correct_option": correct_opt,
        "feedback": feedback,
        "likely_misconception": likely_misc,
        "confidence": conf,
        "reteach_explanation": reteach,
        "follow_up_question": follow_up_question,
        "source": fu_cite or source,
        "attempt": attempt,
        "mastery": snap,
        "cost_usd": cost,
    }
