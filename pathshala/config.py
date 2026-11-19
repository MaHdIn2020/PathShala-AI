"""Central config. All knobs come from env (.env). No pydantic needed."""
import os
from dataclasses import dataclass


def _b(name: str, default: bool) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Config:
    database_url: str
    llm_model: str
    llm_fast_model: str
    llm_verify_model: str
    embed_provider: str  # local | litellm
    embed_model: str
    embed_dim: int
    retrieve_k: int
    rerank_k: int
    min_score: float
    verify: bool
    rewrite: bool
    cache: bool
    rerank: bool
    max_question_chars: int
    max_context_chars: int


def get_config() -> Config:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    llm = os.getenv("LLM_MODEL", "gemini/gemini-flash-latest")
    fast = os.getenv("LLM_FAST_MODEL", llm)
    return Config(
        database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pathshala"),
        llm_model=llm,
        llm_fast_model=fast,
        llm_verify_model=os.getenv("LLM_VERIFY_MODEL", llm),
        embed_provider=os.getenv("EMBED_PROVIDER", "local"),
        embed_model=os.getenv("EMBED_MODEL", "BAAI/bge-m3"),
        embed_dim=int(os.getenv("EMBED_DIM", "1024")),
        retrieve_k=int(os.getenv("RETRIEVE_K", "30")),
        rerank_k=int(os.getenv("RERANK_K", "4")),
        min_score=float(os.getenv("MIN_SCORE", "0.35")),
        verify=_b("VERIFY", True),
        rewrite=_b("REWRITE", True),
        cache=_b("CACHE", True),
        rerank=_b("RERANK", False),
        max_question_chars=int(os.getenv("MAX_QUESTION_CHARS", "600")),
        max_context_chars=int(os.getenv("MAX_CONTEXT_CHARS", "3600")),
    )
