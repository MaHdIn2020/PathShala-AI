"""Grounded tutor pipeline: rewrite -> retrieve -> gate -> answer -> citation check -> verify -> respond.
Dependencies are injectable (retrieve_fn / llm_fn) so tests run without DB or network."""
import hashlib
import time
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .config import get_config
from .text import normalize_bangla

REFUSAL = "এই প্রশ্নের উত্তর পাঠ্যবইয়ে খুঁজে পাইনি।"
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
    "suicide",
    "kill myself",
    "self harm",
    "self-harm",
    "want to die",
)
_PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
_CACHE: dict = {}


def is_distress_query(text: str) -> bool:
    t = normalize_bangla(text).lower()
    return any(k in t for k in _DISTRESS_KEYWORDS)


def load_prompt(name: str) -> str:
    lines = (_PROMPTS / f"{name}.md").read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def format_context(chunks: list[dict], max_chars: int = 6000) -> str:
    parts, used = [], 0
    for c in chunks:
        head = f"[{c['id']}] (শ্রেণি {c.get('class_level', '-')}, {c.get('subject', '-')}, অধ্যায় {c.get('chapter_no', '-')}: {c.get('chapter') or '-'})"
        body = f"{head}\n{c['text']}"
        if used + len(body) > max_chars and parts:
            break
        parts.append(body)
        used += len(body)
    return "\n\n".join(parts)


def clean_citations(citations, chunks: list[dict]) -> list[dict]:
    """Keep only citations whose chunk_id was really retrieved; rebuild every field from chunk metadata.
    The model can never invent a source. (Dataset has no page numbers: cite class/subject/chapter/chunk_ref.)"""
    by_id = {str(c["id"]): c for c in chunks}
    out, seen = [], set()
    for ci in citations or []:
        if not isinstance(ci, dict):
            continue
        c = by_id.get(str(ci.get("chunk_id")))
        if c is None or c["id"] in seen:
            continue
        seen.add(c["id"])
        out.append(
            {
                "chunk_id": c["id"],
                "chunk_ref": c.get("chunk_ref"),
                "book": c.get("book"),
                "class_level": c.get("class_level"),
                "subject": c.get("subject"),
                "chapter_no": c.get("chapter_no"),
                "chapter": c.get("chapter"),
                "page": c.get("page_start"),  # None for Mendeley data; kept for PDF-based books
                "snippet": c["text"][:240],
            }
        )
    return out


def _refuse(reason: str, t0: float, top_score=None, topic=None, cost=0.0, query=None) -> dict:
    return {
        "answer": REFUSAL,
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
    }


def _default_retrieve(query, class_level, subject, cfg):
    from . import retrieval

    return retrieval.search(query, class_level, subject, cfg=cfg)


class PipelineState(TypedDict, total=False):
    question: str
    class_level: int
    subject: str | None
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
        if cfg.rewrite:
            try:
                obj, u = llm_fn(load_prompt("query_rewrite"), q, cfg.llm_fast_model, 300)
                cost += u.get("cost", 0.0)
                query = (obj.get("query") or q).strip() or q
            except Exception:
                query = q
        return {"query": query, "cost": cost}

    def retrieve_node(state: PipelineState) -> dict:
        chunks = retrieve_fn(state["query"], state["class_level"], state.get("subject"), cfg)
        top_score = max((c.get("sim", 0.0) for c in chunks), default=0.0)
        topic = chunks[0].get("chapter") if chunks else None
        if not chunks or top_score < cfg.min_score:
            return {"chunks": chunks, "top_score": top_score, "topic": topic, "refused": True, "reason": "low_retrieval"}
        ctx = format_context(chunks, cfg.max_context_chars)
        return {"chunks": chunks, "top_score": top_score, "topic": topic, "ctx": ctx, "refused": False}

    def answer_node(state: PipelineState) -> dict:
        system = load_prompt("tutor_system").replace("{class}", str(state["class_level"]))
        user_msg = f"CONTEXT:\n{state['ctx']}\n\nQUESTION: {state['question']}"
        if state.get("hint"):
            user_msg += f"\n\nHINT: {state['hint']}"
        obj, u = llm_fn(system, user_msg, cfg.llm_model, 1500)
        cost = state.get("cost", 0.0) + u.get("cost", 0.0)
        ans = (obj.get("answer") or "").strip()
        if not ans or ans == REFUSAL:
            return {"raw_obj": obj, "ans": ans, "cost": cost, "refused": True, "reason": "model_refused"}
        return {"raw_obj": obj, "ans": ans, "cost": cost, "refused": False, "reason": None}

    def check_cites_node(state: PipelineState) -> dict:
        cites = clean_citations(state["raw_obj"].get("citations"), state["chunks"])
        if not cites:
            return {"cites": [], "refused": True, "reason": "no_valid_citation"}
        return {"cites": cites, "refused": False}

    def verify_node(state: PipelineState) -> dict:
        if not cfg.verify:
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


def answer(question: str, class_level: int, subject: str | None = None, *, cfg=None, retrieve_fn=None, llm_fn=None) -> dict:
    cfg = cfg or get_config()
    t0 = time.time()
    q = normalize_bangla(question)[: cfg.max_question_chars]
    if not q:
        return _refuse("empty_question", t0)
    if is_distress_query(q):
        return {**_refuse("safety_distress", t0, query=q), "answer": SAFETY_MESSAGE}

    key = hashlib.sha256(f"{q}|{class_level}|{subject}".encode()).hexdigest()
    if cfg.cache and key in _CACHE:
        return {**_CACHE[key], "cached": True, "latency_ms": int((time.time() - t0) * 1000)}

    retrieve_fn = retrieve_fn or _default_retrieve
    if llm_fn is None:
        from . import llm

        llm_fn = llm.chat_json

    graph = build_graph(cfg, retrieve_fn, llm_fn)
    out = graph.invoke(
        {
            "question": q,
            "class_level": class_level,
            "subject": subject,
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
        return _refuse(out.get("reason") or "refused", t0, top_score, topic, cost, query)

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
    }
    if cfg.cache:
        _CACHE[key] = res
    return res
