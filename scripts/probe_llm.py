"""Probe: one LLM call + one embedding call. Prints model names, latency, cost. Usage: python scripts/probe_llm.py"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathshala.config import get_config  # noqa: E402


def probe_llm(cfg) -> bool:
    from pathshala.llm import chat_text

    t = time.time()
    try:
        text, usage = chat_text("Reply in one short Bangla sentence.", "বাংলাদেশের রাজধানী কী?", cfg.llm_model, max_tokens=60)
    except Exception as e:
        print(f"LLM FAIL  model={cfg.llm_model}  error={type(e).__name__}: {str(e)[:300]}")
        return False
    print(f"LLM OK    model={cfg.llm_model}  latency={time.time() - t:.2f}s  cost=${usage['cost']:.6f}  tokens={usage['prompt']}+{usage['completion']}")
    print(f"          reply: {text}")
    return True


def probe_embed(cfg) -> bool:
    from pathshala.embed import embed_query

    t = time.time()
    try:
        vec = embed_query("সালোকসংশ্লেষণ কী?")
    except Exception as e:
        print(f"EMBED FAIL  provider={cfg.embed_provider} model={cfg.embed_model}  error={type(e).__name__}: {str(e)[:300]}")
        return False
    print(f"EMBED OK  provider={cfg.embed_provider}  model={cfg.embed_model}  dim={len(vec)}  latency={time.time() - t:.2f}s (includes model load)")
    return True


if __name__ == "__main__":
    c = get_config()
    ok_llm = probe_llm(c)
    ok_emb = probe_embed(c)
    sys.exit(0 if ok_llm and ok_emb else 1)

