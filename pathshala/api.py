"""FastAPI app. Run: uvicorn pathshala.api:app --reload --port 8000"""
import json
import logging
import os
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import concept_rescue, db, llm, mastery, pipeline, retrieval
from .config import get_config
from .security import RateLimiter, allowed_origins, verify_teacher_token

app = FastAPI(title="PathShala AI", version="0.2.0")
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

_RATE_LIMITER = RateLimiter(max_per_min=int(os.getenv("RATE_LIMIT_PER_MIN", "60")))
_MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "3200000"))
_LOG = logging.getLogger("pathshala.api")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > _MAX_BODY_BYTES:
        return JSONResponse({"detail": "Request body too large"}, status_code=413)
    if request.url.path not in ("/health", "/health/ready"):
        ip = request.client.host if request.client else "unknown"
        if not _RATE_LIMITER.allow(ip):
            return JSONResponse({"detail": "Too many requests"}, status_code=429)
    if request.url.path.startswith("/teacher"):
        tok = request.headers.get("x-teacher-token") or request.query_params.get("token")
        if not verify_teacher_token(tok):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    try:
        response = await call_next(request)
    except Exception as exc:
        _LOG.warning("unhandled_error req_id=%s path=%s err=%s", req_id, request.url.path, type(exc).__name__)
        return JSONResponse(
            {"detail": "সার্ভার সাময়িকভাবে ব্যস্ত আছে। অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।", "request_id": req_id},
            status_code=503,
            headers={"X-Request-ID": req_id},
        )
    response.headers["X-Request-ID"] = req_id
    return response


class AskReq(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    class_level: int = Field(ge=1, le=12)
    subject: str | None = None
    session_id: str | None = None
    curriculum_id: str = "nctb"
    textbook_medium: str = "bangla_version"
    answer_language: str = "bn"


class FeedbackReq(BaseModel):
    query_id: int
    helpful: bool
    comment: str | None = None


class AskImageReq(BaseModel):
    image_base64: str
    mime_type: str = "image/jpeg"
    class_level: int = Field(ge=1, le=12)
    subject: str | None = None
    session_id: str | None = None
    curriculum_id: str = "nctb"
    textbook_medium: str = "bangla_version"
    answer_language: str = "bn"


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/health/ready")
def health_ready():
    """Readiness check verifying Postgres connectivity and textbook counts by medium."""
    try:
        with db.get_conn() as c, c.cursor() as cur:
            cur.execute(
                "select textbook_medium, count(*) as books from textbooks group by textbook_medium order by textbook_medium"
            )
            books = cur.fetchall()
        return {"ok": True, "db": "ready", "books_by_medium": books}
    except Exception:
        return JSONResponse({"ok": False, "db": "unavailable"}, status_code=503)


@app.get("/curriculum/catalog")
def curriculum_catalog():
    """Return genuinely available (curriculum_id, textbook_medium, class_level, subject) combinations."""
    books = db.get_curriculum_catalog()
    return {"books": books, "total_books": len(books)}


@app.post("/ask")
def ask(req: AskReq):
    res = pipeline.answer(
        req.question,
        req.class_level,
        req.subject,
        curriculum_id=req.curriculum_id,
        textbook_medium=req.textbook_medium,
        answer_language=req.answer_language,
    )
    res["query_id"] = (
        None
        if res.get("reason") == "safety_distress"
        else db.log_query(
            {
                "session_id": req.session_id,
                "curriculum_id": req.curriculum_id,
                "textbook_medium": req.textbook_medium,
                "answer_language": req.answer_language,
                "class_level": req.class_level,
                "subject": req.subject,
                "question": req.question[:600],
                "topic": res.get("topic"),
                "top_score": res.get("top_score"),
                "refused": res["refused"],
                "reason": res.get("reason"),
                "latency_ms": res["latency_ms"],
                "cost_usd": res["cost_usd"],
            }
        )
    )
    return res


WARMUP_QUESTIONS = [
    {"class_level": 5, "subject": "science", "question": "খাদ্যশৃঙ্খল কাকে বলে?"},
    {"class_level": 5, "subject": "bangla", "question": "বাংলাদেশে বসবাসকারী ক্ষুদ্র নৃগোষ্ঠীর মাতৃভাষা কী কী?"},
    {"class_level": 5, "subject": "bgs", "question": "লালবাগ কেল্লা কোথায় অবস্থিত?"},
    {"class_level": 3, "subject": "bangla", "question": "আমাদের গ্রাম কবিতায় গ্রামের মানুষ কীভাবে থাকে?"},
    {"class_level": 4, "subject": "science", "question": "উদ্ভিদ কীভাবে খাদ্য তৈরি করে?"},
    {"class_level": 5, "subject": "science", "question": "বায়ুদূষণ কী?"},
    {"class_level": 4, "subject": "bgs", "question": "বাংলাদেশের প্রধান নদীগুলোর নাম কী?"},
    {"class_level": 3, "subject": "science", "question": "পানির তিনটি অবস্থা কী কী?"},
]


@app.post("/ask/stream")
def ask_stream(req: AskReq):
    """SSE endpoint: emits status immediately, then answer chunks and final JSON payload."""
    def event_gen():
        search_msg = (
            "Searching selected textbook..." if req.answer_language == "en" else "পাঠ্যবই খোঁজা হচ্ছে..."
        )
        yield f"data: {json.dumps({'type': 'status', 'message': search_msg}, ensure_ascii=False)}\n\n"
        res = pipeline.answer(
            req.question,
            req.class_level,
            req.subject,
            curriculum_id=req.curriculum_id,
            textbook_medium=req.textbook_medium,
            answer_language=req.answer_language,
        )
        cites = res.get("citations") or []
        if cites and not res.get("refused"):
            c0 = cites[0]
            found_msg = f"পাওয়া গেছে: শ্রেণি {c0.get('class_level', req.class_level)} · {c0.get('subject') or ''} · অধ্যায় {c0.get('chapter_no') or '-'}"
            yield f"data: {json.dumps({'type': 'status', 'message': found_msg}, ensure_ascii=False)}\n\n"
        res["query_id"] = (
            None
            if res.get("reason") == "safety_distress"
            else db.log_query(
                {
                    "session_id": req.session_id,
                    "curriculum_id": req.curriculum_id,
                    "textbook_medium": req.textbook_medium,
                    "answer_language": req.answer_language,
                    "class_level": req.class_level,
                    "subject": req.subject,
                    "question": req.question[:600],
                    "topic": res.get("topic"),
                    "top_score": res.get("top_score"),
                    "refused": res["refused"],
                    "reason": res.get("reason"),
                    "latency_ms": res["latency_ms"],
                    "cost_usd": res["cost_usd"],
                }
            )
        )
        ans = res.get("answer") or ""
        step = max(24, len(ans) // 6) if ans else 24
        for i in range(0, len(ans), step):
            yield f"data: {json.dumps({'type': 'delta', 'text': ans[i : i + step]}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'payload': res}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/warmup")
def warmup():
    """Pre-warm in-memory answer cache with the 8 home-page sample questions."""
    warmed = 0
    for item in WARMUP_QUESTIONS:
        try:
            pipeline.answer(item["question"], item["class_level"], item["subject"])
            warmed += 1
        except Exception:
            pass
    return {"warmed": warmed, "total": len(WARMUP_QUESTIONS)}


@app.post("/ask-image")
def ask_image(req: AskImageReq):
    """Photo input: 2MB limit, no image storage. Transcribes question then calls answer pipeline."""
    if len(req.image_base64) > 2_800_000:
        raise HTTPException(413, "চিত্রের আকার ২ মেগাবাইট (2MB) এর বেশি হতে পারবে না।")

    system = pipeline.load_prompt("vision_ocr")
    cfg = get_config()
    ocr_res, usage = llm.chat_image_json(
        system=system,
        image_base64=req.image_base64,
        mime_type=req.mime_type,
        model=cfg.llm_model,
        max_tokens=400,
    )
    extracted_q = (ocr_res.get("question") or "").strip()
    if not extracted_q or extracted_q.lower() == "[unreadable]":
        return {
            "answer": "ছবি থেকে প্রশ্নটি স্পষ্টভাবে পড়া যায়নি। অনুগ্রহ করে আবার পরিষ্কার ছবি তুলুন।",
            "steps": [],
            "citations": [],
            "confidence": 0.0,
            "refused": True,
            "reason": "unreadable_image",
            "top_score": 0.0,
            "topic": None,
            "latency_ms": 0,
            "cost_usd": usage.get("cost", 0.0),
            "cached": False,
            "query": None,
        }

    res = pipeline.answer(
        extracted_q,
        req.class_level,
        req.subject,
        curriculum_id=req.curriculum_id,
        textbook_medium=req.textbook_medium,
        answer_language=req.answer_language,
    )
    res["transcribed_question"] = extracted_q
    res["cost_usd"] = res.get("cost_usd", 0.0) + usage.get("cost", 0.0)
    res["query_id"] = (
        None
        if res.get("reason") == "safety_distress"
        else db.log_query(
            {
                "session_id": req.session_id,
                "curriculum_id": req.curriculum_id,
                "textbook_medium": req.textbook_medium,
                "answer_language": req.answer_language,
                "class_level": req.class_level,
                "subject": req.subject,
                "question": extracted_q[:600],
                "topic": res.get("topic"),
                "top_score": res.get("top_score"),
                "refused": res["refused"],
                "reason": res.get("reason"),
                "latency_ms": res["latency_ms"],
                "cost_usd": res["cost_usd"],
            }
        )
    )
    return res


@app.post("/search")
def search(req: AskReq):
    chunks = retrieval.search(
        req.question,
        req.class_level,
        req.subject,
        curriculum_id=req.curriculum_id,
        textbook_medium=req.textbook_medium,
    )
    return [{k: v for k, v in c.items() if k not in ("contextual_text",)} for c in chunks]


@app.post("/practice")
def practice(req: AskReq):
    """3 practice questions on a topic (the `question` field), grounded in retrieved chunks."""
    from . import practice as practice_mod

    return practice_mod.practice(req.question, req.class_level, req.subject)


class PracticeAttemptReq(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    class_level: int = Field(ge=1, le=12)
    subject: str | None = None
    chapter: str = Field(min_length=1, max_length=200)
    correct: bool
    curriculum_id: str = "nctb"
    textbook_medium: str = "bangla_version"
    event_key: str | None = None


@app.post("/practice/attempt")
def practice_attempt(req: PracticeAttemptReq):
    """Update anonymous session EWMA mastery for a chapter after a practice answer."""
    updated = mastery.record_attempt(
        req.session_id,
        req.class_level,
        req.subject or "general",
        req.chapter,
        req.correct,
        curriculum_id=req.curriculum_id,
        textbook_medium=req.textbook_medium,
        event_key=req.event_key,
        use_db=True,
    )
    snap = mastery.get_session_mastery(req.session_id, use_db=True)
    return {"updated": updated, "mastery": snap}


@app.get("/mastery")
def get_mastery(session_id: str = "anon"):
    return mastery.get_session_mastery(session_id, use_db=True)


class ConceptCheckReq(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(default="", max_length=4000)
    class_level: int = Field(ge=1, le=12)
    subject: str | None = None
    curriculum_id: str = "nctb"
    textbook_medium: str = "bangla_version"
    answer_language: str = "bn"
    chunk_id: int | None = None
    learning_objective: str | None = None
    exclude_questions: list[str] = Field(default_factory=list)


@app.post("/concept-rescue/check")
def concept_rescue_check(req: ConceptCheckReq):
    """Generate a grounded diagnostic MCQ for the student's current concept."""
    return concept_rescue.generate_diagnostic_check(
        req.question,
        req.answer,
        req.class_level,
        req.subject,
        curriculum_id=req.curriculum_id,
        textbook_medium=req.textbook_medium,
        answer_language=req.answer_language,
        chunk_id=req.chunk_id,
        learning_objective=req.learning_objective,
        exclude_questions=req.exclude_questions,
    )


class ConceptSubmitReq(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    diagnostic: dict
    selected_option: str = Field(min_length=1, max_length=4)
    event_key: str | None = None
    answer_language: str | None = None


@app.post("/concept-rescue/submit")
def concept_rescue_submit(req: ConceptSubmitReq):
    """Evaluate diagnostic answer, diagnose likely misconception, re-teach simpler, and update mastery."""
    try:
        return concept_rescue.submit_diagnostic_answer(
            req.session_id,
            req.diagnostic,
            req.selected_option,
            event_key=req.event_key,
            answer_language=req.answer_language,
            use_db=True,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    """Delete anonymous session learning events, mastery state, and query history."""
    return {"ok": True, "deleted": mastery.delete_session(session_id, use_db=True)}


class ExplainEnReq(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)
    question: str = Field(default="", max_length=600)


@app.post("/explain-en")
def explain_en(req: ExplainEnReq):
    """Explain an already-grounded textbook answer in simple English without adding external facts."""
    system = (
        "Translate and explain the given textbook answer in simple, clear English. "
        "Do NOT add any facts that are not in the provided answer. Keep it concise (2-4 sentences)."
    )
    user = f"QUESTION: {req.question}\nTEXTBOOK ANSWER:\n{req.answer}"
    text, usage = llm.chat_text(system, user, get_config().llm_fast_model, max_tokens=300)
    return {"english": text, "cost_usd": usage.get("cost", 0.0)}


@app.post("/baseline")
def baseline(req: AskReq):
    """Plain LLM, no retrieval. Used only by eval to show RAG gain."""
    text, usage = llm.plain_answer(req.question, req.class_level, get_config().llm_model)
    return {"answer": text, "citations": [], "refused": False, "cost_usd": usage["cost"]}


@app.post("/feedback")
def feedback(req: FeedbackReq):
    return {"ok": db.log_feedback(req.query_id, req.helpful, req.comment)}


@app.get("/cite/{chunk_id}")
def cite(chunk_id: int):
    c = db.get_chunk(chunk_id)
    if not c:
        raise HTTPException(404, "chunk not found")
    return c


@app.get("/teacher/topics")
def teacher_topics(limit: int = 50):
    return db.topic_counts(limit)


@app.post("/telegram/webhook")
def telegram_webhook(update: dict):
    """Lightweight Telegram bot webhook proof using the same grounded pipeline."""
    msg = update.get("message") or {}
    text = (msg.get("text") or "").strip()
    chat_id = (msg.get("chat") or {}).get("id")
    if not text:
        return {"ok": True, "reply": ""}
    res = pipeline.answer(text, class_level=5, subject=None)
    reply = res.get("answer") or pipeline.REFUSAL
    cites = res.get("citations") or []
    if cites and not res.get("refused"):
        c0 = cites[0]
        reply += f"\n\n[উৎস: শ্রেণি {c0.get('class_level', 5)} · {c0.get('chapter') or c0.get('chunk_ref')}]"
    return {"ok": True, "chat_id": chat_id, "reply": reply, "refused": bool(res.get("refused"))}


@app.get("/teacher/summary")
def teacher_summary(limit: int = 50):
    data = db.teacher_summary(limit)
    if isinstance(data, dict):
        data["adaptive_mastery"] = mastery.get_aggregate_mastery(use_db=True)
        tot = int(data.get("total_queries") or 0)
        ref = int(data.get("refused_queries") or 0)
        fb_up = int(data.get("helpful_count") or 0)
        fb_tot = int(data.get("feedback_count") or 0)
        data["refusal_rate"] = round(ref / tot, 4) if tot else 0.0
        data["helpful_rate"] = round(fb_up / fb_tot, 4) if fb_tot else None
    return data


@app.get("/teacher/export/weak-chapters.csv")
def teacher_export_weak_chapters():
    """Download weak chapters CSV for teacher assignment planning."""
    return PlainTextResponse(
        content=mastery.weak_chapters_csv(use_db=True),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="weak_chapters.csv"'},
    )


@app.get("/teacher/clusters")
def teacher_clusters(k: int = 6, use_llm: bool = False):
    from . import clustering

    return clustering.cluster_db_queries(k=k, use_llm=use_llm)
