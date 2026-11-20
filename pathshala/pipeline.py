"""Grounded tutor pipeline: rewrite -> retrieve -> gate -> answer -> citation check -> verify -> respond.
Strictly isolates textbook_medium from answer_language. Dependencies are injectable for offline tests."""
import hashlib
import re
import time
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .config import get_config
from .text import normalize_bangla, normalize_for_retrieval

REFUSAL = "এই প্রশ্নের উত্তর পাঠ্যবইয়ে খুঁজে পাইনি।"
REFUSAL_EN = "I could not find the answer to this question in the selected textbook."
UNAVAILABLE_BN = (
    "নির্বাচিত কারিকুলাম, পাঠ্যবইয়ের মাধ্যম, শ্রেণি বা বিষয়টি বর্তমানে ডেটাবেসে সংরক্ষিত নেই। "
    "অনুগ্রহ করে উপলব্ধ পাঠ্যবই নির্বাচন করুন।"
)
UNAVAILABLE_EN = (
    "The selected curriculum, textbook version, class, or subject is not currently loaded. "
    "Please choose an available textbook combination."
)
SAFETY_MESSAGE = (
    "তোমার কথা শুনে মনে হচ্ছে তুমি খুব কঠিন সময় পার করছ। তুমি একা নও—অনুগ্রহ করে এখনই মা-বাবা, শিক্ষক বা "
    "পরিবারের কোনো বিশ্বস্ত বড় মানুষের সাথে কথা বলো। জরুরি সহায়তার জন্য শিশু সহায়তা হেল্পলাইন ১০৯৮ (1098) "
    "বা কান পেতে রই হেল্পলাইনে যোগাযোগ করতে পারো।"
)
_DISTRESS_KEYWORDS = (
    "আত্মহত্যা",
    "মরে যেতে চাই",
    "বাঁচতে চাই না",
    "নিজেকে শেষ",
    "মরতে চাই",
    "নিজের ক্ষতি",
    "নিজেকে মেরে",
    "বাঁচতে ইচ্ছা করে না",
    "জীবন শেষ",
    "নিজের প্রাণ",
    "suicide",
    "suicidal",
    "kill myself",
    "self harm",
    "self-harm",
    "hurt myself",
    "want to die",
    "end my life",
    "don't want to live",
    "do not want to live",
    "no reason to live",
    "more jete chai",
    "bachte chai na",
    "bachte iccha kore na",
    "atmahatya",
    "nijeke shesh",
    "nijeke mere",
    "jibon shesh",
)
_PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
_CACHE: dict = {}
_HAS_BN = re.compile(r"[\u0980-\u09FF]")


def refusal_text(answer_language: str = "bn") -> str:
    return REFUSAL_EN if answer_language == "en" else REFUSAL


def is_distress_query(text: str) -> bool:
    t = normalize_bangla(text).lower()
    return any(k in t for k in _DISTRESS_KEYWORDS)


def load_prompt(name: str) -> str:
    lines = (_PROMPTS / f"{name}.md").read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


_SUBJECT_MIN_SCORE = {
    "math": 0.42,
    "english": 0.42,
    "science": 0.45,
    "bangla": 0.45,
    "bgs": 0.45,
}


def subject_min_score(subject: str | None, default_score: float) -> float:
    """Per-subject retrieval threshold (never below 0.35 to preserve 100% off-syllabus refusal)."""
    if not subject:
        return default_score
    return max(0.35, _SUBJECT_MIN_SCORE.get(subject.strip().lower(), default_score))


def needs_cross_lang_rewrite(query: str, textbook_medium: str = "bangla_version") -> bool:
    """True when query language differs from textbook_medium script so search terms need translation."""
    has_bn = bool(_HAS_BN.search(query or ""))
    if textbook_medium == "english_version" and has_bn:
        return True
    if textbook_medium == "bangla_version" and not has_bn and bool(re.search(r"[A-Za-z]", query or "")):
        return True
    return False


def should_rewrite(
    query: str,
    subject: str | None,
    min_chars: int = 45,
    textbook_medium: str = "bangla_version",
) -> bool:
    """Run query rewrite when subject is unknown, query is long, or query script differs from textbook medium."""
    return (not subject) or (len(query.strip()) > min_chars) or needs_cross_lang_rewrite(query, textbook_medium)


def should_skip_verify(top_score: float | None, cites: list[dict], threshold: float = 0.85) -> bool:
    """Skip verifier LLM call when retrieval score is very high and citations are valid."""
    return bool(cites) and top_score is not None and top_score >= threshold


def format_context(chunks: list[dict], max_chars: int = 3600, max_chunks: int = 4, max_chunk_chars: int = 800) -> str:
    parts, used = [], 0
    for c in chunks[:max_chunks]:
        pg = ""
        if c.get("page_start") is not None:
            pg_end = c.get("page_end")
            pg = f", pp. {c['page_start']}-{pg_end}" if pg_end and pg_end != c["page_start"] else f", p. {c['page_start']}"
        med = c.get("textbook_medium") or "-"
        head = f"[{c['id']}] (Class {c.get('class_level', '-')}, {med}, {c.get('subject', '-')}, Ch {c.get('chapter_no', '-')}: {c.get('chapter') or '-'}{pg})"
        text = (c.get("text") or "")[:max_chunk_chars]
        body = f"{head}\n{text}"
        if used + len(body) > max_chars and parts:
            break
        parts.append(body)
        used += len(body)
    return "\n\n".join(parts)


def clean_citations(citations, chunks: list[dict], expected_medium: str | None = None) -> list[dict]:
    """Keep only citations whose chunk_id was really retrieved and matches expected_medium; rebuild metadata from DB."""
    by_id = {str(c["id"]): c for c in chunks}
    out, seen = [], set()
    for ci in citations or []:
        raw_id = ci.get("chunk_id", ci.get("id")) if isinstance(ci, dict) else ci
        if raw_id is None:
            continue
        c = by_id.get(str(raw_id))
        if c is None or c["id"] in seen:
            continue
        if expected_medium and c.get("textbook_medium") and c.get("textbook_medium") != expected_medium:
            continue
        seen.add(c["id"])
        out.append(
            {
                "chunk_id": c["id"],
                "chunk_ref": c.get("chunk_ref"),
                "book": c.get("book"),
                "curriculum_id": c.get("curriculum_id") or "nctb",
                "textbook_medium": c.get("textbook_medium") or expected_medium or "bangla_version",
                "class_level": c.get("class_level"),
                "subject": c.get("subject"),
                "chapter_no": c.get("chapter_no"),
                "chapter": c.get("chapter"),
                "page": c.get("page_start"),
                "page_start": c.get("page_start"),
                "page_end": c.get("page_end"),
                "snippet": c["text"][:240],
            }
        )
    return out


def _refuse(
    reason: str,
    t0: float,
    top_score=None,
    topic=None,
    cost=0.0,
    query=None,
    *,
    answer_language: str = "bn",
    curriculum_id: str = "nctb",
    textbook_medium: str = "bangla_version",
    custom_answer: str | None = None,
) -> dict:
    return {
        "answer": custom_answer or refusal_text(answer_language),
        "steps": [],
        "citations": [],
        "confidence": 0.0,
        "refused": True,
        "reason": reason,
        "top_score": top_score,
        "topic": topic,
        "latency_ms": int((time.time() - t0) * 1000),
        "cost_usd": cost,
        "cached": False,
        "query": query,
        "curriculum_id": curriculum_id,
        "textbook_medium": textbook_medium,
        "answer_language": answer_language,
    }


def _default_retrieve(query, class_level, subject, cfg, *, curriculum_id="nctb", textbook_medium="bangla_version"):
    from . import retrieval

    return retrieval.search(
        query,
        class_level,
        subject,
        cfg=cfg,
        curriculum_id=curriculum_id,
        textbook_medium=textbook_medium,
    )


def _call_retrieve(retrieve_fn, query, class_level, subject, cfg, curriculum_id, textbook_medium):
    try:
        return retrieve_fn(
            query,
            class_level,
            subject,
            cfg,
            curriculum_id=curriculum_id,
            textbook_medium=textbook_medium,
        )
    except TypeError:
        return retrieve_fn(query, class_level, subject, cfg)


class PipelineState(TypedDict, total=False):
    question: str
    class_level: int
    subject: str | None
    curriculum_id: str
    textbook_medium: str
    answer_language: str
    query: str
    chunks: list[dict]
    top_score: float
    topic: str | None
    ctx: str
    raw_obj: dict
    ans: str
    cites: list[dict]
    hint: str | None
    retries: int
    cost: float
    reason: str | None
    refused: bool


def build_graph(cfg, retrieve_fn, llm_fn):
    """Build LangGraph tutor pipeline with conditional verify->answer retry loop."""

    def rewrite_node(state: PipelineState) -> dict:
        q = state["question"]
        query = q
        cost = state.get("cost", 0.0)
        med = state.get("textbook_medium", "bangla_version")
        if cfg.rewrite and should_rewrite(q, state.get("subject"), textbook_medium=med):
            target_lang = "English" if med == "english_version" else "Bangla"
            sys_prompt = load_prompt("query_rewrite").replace("{target_lang}", target_lang)
            try:
                obj, u = llm_fn(sys_prompt, q, cfg.llm_fast_model, 300)
                cost += u.get("cost", 0.0)
                query = (obj.get("query") or q).strip() or q
            except Exception:
                query = q
        return {"query": query, "cost": cost}

    def retrieve_node(state: PipelineState) -> dict:
        retrieval_q = normalize_for_retrieval(state["query"])
        chunks = _call_retrieve(
            retrieve_fn,
            retrieval_q,
            state["class_level"],
            state.get("subject"),
            cfg,
            state.get("curriculum_id", "nctb"),
            state.get("textbook_medium", "bangla_version"),
        )
        top_score = max((c.get("sim", 0.0) for c in chunks), default=0.0)
        topic = chunks[0].get("chapter") if chunks else None
        threshold = subject_min_score(state.get("subject"), cfg.min_score)
        if not chunks or top_score < threshold:
            return {"chunks": chunks, "top_score": top_score, "topic": topic, "refused": True, "reason": "low_retrieval"}
        ctx = format_context(chunks, cfg.max_context_chars)
        return {"chunks": chunks, "top_score": top_score, "topic": topic, "ctx": ctx, "refused": False}

    def answer_node(state: PipelineState) -> dict:
        ans_lang = state.get("answer_language", "bn")
        med = state.get("textbook_medium", "bangla_version")
        lang_label = "English" if ans_lang == "en" else "Bangla (বাংলা)"
        med_label = "NCTB English Version" if med == "english_version" else "NCTB Bangla Version"
        ref_txt = refusal_text(ans_lang)
        system = (
            load_prompt("tutor_system")
            .replace("{class}", str(state["class_level"]))
            .replace("{answer_language}", lang_label)
            .replace("{textbook_medium}", med_label)
            .replace("{refusal}", ref_txt)
        )
        user_msg = f"CONTEXT:\n{state['ctx']}\n\nQUESTION: {state['question']}"
        if state.get("hint"):
            user_msg += f"\n\nHINT: {state['hint']}"
        obj, u = llm_fn(system, user_msg, cfg.llm_model, 1500)
        cost = state.get("cost", 0.0) + u.get("cost", 0.0)
        ans = (obj.get("answer") or "").strip()
        if not ans or ans == REFUSAL or ans == REFUSAL_EN:
            return {"raw_obj": obj, "ans": ans, "cost": cost, "refused": True, "reason": "model_refused"}
        return {"raw_obj": obj, "ans": ans, "cost": cost, "refused": False, "reason": None}

    def check_cites_node(state: PipelineState) -> dict:
        cites = clean_citations(
            state["raw_obj"].get("citations"),
            state["chunks"],
            expected_medium=state.get("textbook_medium"),
        )
        if not cites:
            return {"cites": [], "refused": True, "reason": "no_valid_citation"}
        return {"cites": cites, "refused": False}

    def verify_node(state: PipelineState) -> dict:
        if not cfg.verify or should_skip_verify(state.get("top_score"), state.get("cites") or []):
            return {"refused": False, "reason": None}
        cost = state.get("cost", 0.0)
        try:
            v, u2 = llm_fn(load_prompt("verifier"), f"ANSWER:\n{state['ans']}\n\nCONTEXT:\n{state['ctx']}", cfg.llm_verify_model, 400)
            cost += u2.get("cost", 0.0)
        except Exception:
            return {"cost": cost, "refused": True, "reason": "verifier_error"}

        if str(v.get("verdict", "")).upper() == "PASS":
            return {"cost": cost, "refused": False, "reason": None}
        if state.get("retries", 0) < 1:
            return {
                "cost": cost,
                "retries": state.get("retries", 0) + 1,
                "hint": "fix unsupported claims: use only facts from CONTEXT and cite valid chunk_id",
                "reason": "retry_verify",
                "refused": False,
            }
        return {"cost": cost, "refused": True, "reason": "verifier_fail"}

    g = StateGraph(PipelineState)
    g.add_node("rewrite", rewrite_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("answer", answer_node)
    g.add_node("check_cites", check_cites_node)
    g.add_node("verify", verify_node)

    g.set_entry_point("rewrite")
    g.add_edge("rewrite", "retrieve")
    g.add_conditional_edges("retrieve", lambda s: END if s.get("refused") else "answer")
    g.add_conditional_edges("answer", lambda s: END if s.get("refused") else "check_cites")
    g.add_conditional_edges("check_cites", lambda s: END if s.get("refused") else "verify")
    g.add_conditional_edges("verify", lambda s: "answer" if s.get("reason") == "retry_verify" else END)
    return g.compile()


def answer(
    question: str,
    class_level: int,
    subject: str | None = None,
    *,
    curriculum_id: str = "nctb",
    textbook_medium: str = "bangla_version",
    answer_language: str = "bn",
    cfg=None,
    retrieve_fn=None,
    llm_fn=None,
    availability_fn=None,
) -> dict:
    cfg = cfg or get_config()
    t0 = time.time()
    curr = (curriculum_id or "nctb").strip().lower()
    med = (textbook_medium or "bangla_version").strip().lower()
    ans_lang = "en" if str(answer_language or "bn").strip().lower() == "en" else "bn"

    q = normalize_bangla(question)[: cfg.max_question_chars]
    if not q:
        return _refuse("empty_question", t0, answer_language=ans_lang, curriculum_id=curr, textbook_medium=med)
    if is_distress_query(q):
        return _refuse(
            "safety_distress",
            t0,
            query=q,
            answer_language=ans_lang,
            curriculum_id=curr,
            textbook_medium=med,
            custom_answer=SAFETY_MESSAGE,
        )

    if availability_fn is not None:
        avail = bool(availability_fn(class_level, subject, med, curr))
    elif retrieve_fn is None:
        from . import db

        avail = db.is_curriculum_available(class_level, subject, textbook_medium=med, curriculum_id=curr, cfg=cfg)
    else:
        avail = True

    if not avail:
        msg = UNAVAILABLE_EN if ans_lang == "en" else UNAVAILABLE_BN
        return _refuse(
            "unavailable_curriculum",
            t0,
            query=q,
            answer_language=ans_lang,
            curriculum_id=curr,
            textbook_medium=med,
            custom_answer=msg,
        )

    key = hashlib.sha256(f"{curr}|{med}|{class_level}|{subject}|{ans_lang}|{q}".encode()).hexdigest()
    if cfg.cache and key in _CACHE:
        return {**_CACHE[key], "cached": True, "latency_ms": int((time.time() - t0) * 1000)}

    use_retrieve = retrieve_fn or _default_retrieve
    if llm_fn is None:
        from . import llm

        llm_fn = llm.chat_json

    graph = build_graph(cfg, use_retrieve, llm_fn)
    out = graph.invoke(
        {
            "question": q,
            "class_level": class_level,
            "subject": subject,
            "curriculum_id": curr,
            "textbook_medium": med,
            "answer_language": ans_lang,
            "query": q,
            "retries": 0,
            "cost": 0.0,
            "refused": False,
        }
    )

    cost = out.get("cost", 0.0)
    top_score = out.get("top_score")
    topic = out.get("topic")
    query = out.get("query", q)
    if out.get("refused"):
        return _refuse(
            out.get("reason") or "refused",
            t0,
            top_score,
            topic,
            cost,
            query,
            answer_language=ans_lang,
            curriculum_id=curr,
            textbook_medium=med,
        )

    obj = out.get("raw_obj") or {}
    res = {
        "answer": out.get("ans") or "",
        "steps": [s for s in (obj.get("steps") or []) if isinstance(s, str)],
        "citations": out.get("cites") or [],
        "confidence": float(obj.get("confidence") or 0.0),
        "refused": False,
        "reason": None,
        "top_score": top_score,
        "topic": topic,
        "latency_ms": int((time.time() - t0) * 1000),
        "cost_usd": cost,
        "cached": False,
        "query": query,
        "curriculum_id": curr,
        "textbook_medium": med,
        "answer_language": ans_lang,
    }
    if cfg.cache:
        _CACHE[key] = res
    return res
