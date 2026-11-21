"""Practice questions grounded in retrieved chunks. Dependencies injectable (no DB/network in tests)."""
from .config import get_config
from .pipeline import REFUSAL, format_context, load_prompt
from .text import normalize_bangla

N_QUESTIONS = 3


def practice(
    topic: str,
    class_level: int,
    subject: str | None = None,
    *,
    curriculum_id: str = "nctb",
    textbook_medium: str = "bangla_version",
    cfg=None,
    retrieve_fn=None,
    llm_fn=None,
) -> dict:
    """Returns {questions: [{q, a, level, chunk_id, chunk_ref}], refused, reason, topic, cost_usd}.
    Every question must cite a chunk that was really retrieved; others are dropped. Needs all 3 or it refuses."""
    cfg = cfg or get_config()
    t = normalize_bangla(topic)[: cfg.max_question_chars]
    if not t:
        return _empty("empty_topic")
    if retrieve_fn is None:
        from . import retrieval

        def retrieve_fn(q, c, s, cf):
            return retrieval.search(
                q,
                c,
                s,
                cfg=cf,
                curriculum_id=curriculum_id,
                textbook_medium=textbook_medium,
            )

    if llm_fn is None:
        from . import llm

        llm_fn = llm.chat_json

    chunks = retrieve_fn(t, class_level, subject, cfg)
    top = max((c.get("sim", 0.0) for c in chunks), default=0.0)
    if not chunks or top < cfg.min_score:
        return _empty("low_retrieval", t)

    ctx = format_context(chunks, cfg.max_context_chars)
    obj, u = llm_fn(load_prompt("practice"), f"CONTEXT:\n{ctx}\n\nTOPIC: {t}", cfg.llm_model, 1200)
    cost = u.get("cost", 0.0)
    by_id = {str(c["id"]): c for c in chunks}
    out = []
    for item in obj.get("questions") or []:
        if not isinstance(item, dict):
            continue
        c = by_id.get(str(item.get("chunk_id")))
        q, a = str(item.get("q") or "").strip(), str(item.get("a") or "").strip()
        if c is None or not q or not a:
            continue
        out.append({"q": q, "a": a, "level": str(item.get("level") or ""), "chunk_id": c["id"], "chunk_ref": c.get("chunk_ref")})
    if len(out) < N_QUESTIONS:
        return {**_empty("not_enough_grounded_questions", t), "cost_usd": cost}
    return {"questions": out[:N_QUESTIONS], "refused": False, "reason": None, "topic": t, "cost_usd": cost}


def _empty(reason: str, topic: str | None = None) -> dict:
    return {"questions": [], "refused": True, "reason": reason, "message": REFUSAL, "topic": topic, "cost_usd": 0.0}
