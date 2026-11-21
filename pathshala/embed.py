"""Embeddings. EMBED_PROVIDER=local -> sentence-transformers (bge-m3, 1024-d, CUDA auto-selected); litellm -> hosted API."""
from .config import get_config

_model = None
_device = None


def _local(texts: list[str], model_name: str) -> list[list[float]]:
    global _model, _device
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer

        _device = "cuda" if torch.cuda.is_available() else "cpu"
        # bfloat16 + max_seq_length 512 keep VRAM (~1.1 GB on RTX 4060) and CPU RAM low
        _model = SentenceTransformer(model_name, device=_device, model_kwargs={"torch_dtype": torch.bfloat16})
        _model.max_seq_length = 512
    bs = 64 if _device == "cuda" else 4
    return _model.encode(texts, normalize_embeddings=True, batch_size=bs, show_progress_bar=False).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    cfg = get_config()
    if cfg.embed_provider == "litellm":
        import litellm

        r = litellm.embedding(model=cfg.embed_model, input=texts)
        vecs = [d["embedding"] for d in r.data]
    else:
        vecs = _local(texts, cfg.embed_model)
    if vecs and len(vecs[0]) != cfg.embed_dim:
        raise ValueError(f"embed dim {len(vecs[0])} != EMBED_DIM {cfg.embed_dim}; fix .env and db/schema.sql")
    return vecs


def embed_query(q: str) -> list[float]:
    return embed_texts([q])[0]


def to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
