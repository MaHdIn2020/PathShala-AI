"""FastAPI app. Run: uvicorn pathshala.api:app --reload --port 8000"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db, llm, pipeline, retrieval
from .config import get_config

app = FastAPI(title="PathShala AI", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AskReq(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    class_level: int = Field(ge=1, le=12)
    subject: str | None = None
    session_id: str | None = None


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


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/ask")
def ask(req: AskReq):
    res = pipeline.answer(req.question, req.class_level, req.subject)
    res["query_id"] = db.log_query(
        {
            "session_id": req.session_id,
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
    return res


@app.post("/ask-image")
def ask_image(req: AskImageReq):
    """Photo input: 2MB limit, no image storage. Transcribes question then calls answer pipeline."""
    # 2MB base64 check (~2.8M characters)
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

    res = pipeline.answer(extracted_q, req.class_level, req.subject)
    res["transcribed_question"] = extracted_q
    res["cost_usd"] = res.get("cost_usd", 0.0) + usage.get("cost", 0.0)
    res["query_id"] = db.log_query(
        {
            "session_id": req.session_id,
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
    return res


@app.post("/search")
def search(req: AskReq):
    chunks = retrieval.search(req.question, req.class_level, req.subject)
    return [{k: v for k, v in c.items() if k not in ("contextual_text",)} for c in chunks]


@app.post("/practice")
def practice(req: AskReq):
    """3 practice questions on a topic (the `question` field), grounded in retrieved chunks."""
    from . import practice as practice_mod

    return practice_mod.practice(req.question, req.class_level, req.subject)


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


@app.get("/teacher/summary")
def teacher_summary(limit: int = 50):
    return db.teacher_summary(limit)


@app.get("/teacher/clusters")
def teacher_clusters(k: int = 6, use_llm: bool = False):
    from . import clustering

    return clustering.cluster_db_queries(k=k, use_llm=use_llm)
