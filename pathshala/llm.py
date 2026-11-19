"""LLM wrapper over LiteLLM (routing + cost logging). litellm imported lazily."""
import json
import re


def parse_json(text: str) -> dict:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE)
    try:
        return json.loads(t)
    except Exception:
        i, j = t.find("{"), t.rfind("}")
        if i != -1 and j > i:
            try:
                return json.loads(t[i : j + 1])
            except Exception:
                pass
    return {}


def _litellm():
    """Import litellm lazily; drop params a given model does not support (e.g. temperature)."""
    import litellm

    litellm.drop_params = True
    return litellm


def _cost(r) -> float:
    try:
        litellm = _litellm()

        return float(litellm.completion_cost(completion_response=r) or 0.0)
    except Exception:
        return 0.0


_FALLBACK_MODELS = (
    "gemini/gemini-flash-lite-latest",
    "gemini/gemini-3-flash-preview",
    "gemini/gemini-3.1-flash-lite",
)


def _complete(model: str, **kwargs):
    """Run litellm.completion with fast timeout and fallback on transient 503 / rate-limit errors."""
    litellm = _litellm()
    models = [model] + [m for m in _FALLBACK_MODELS if m != model]
    last_err = None
    for m in models:
        try:
            return litellm.completion(model=m, timeout=20, num_retries=0, **kwargs)
        except Exception as e:
            msg = str(e)
            if any(code in msg or code in type(e).__name__ for code in ("503", "UNAVAILABLE", "ServiceUnavailable", "RateLimit", "429", "Timeout", "timeout")):
                last_err = e
                continue
            raise
    raise last_err


def chat_json(system: str, user: str, model: str, max_tokens: int = 1500):
    """Returns (obj, usage). obj={} if model output was not valid JSON."""
    r = _complete(
        model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    u = getattr(r, "usage", None)
    usage = {
        "prompt": getattr(u, "prompt_tokens", 0) or 0,
        "completion": getattr(u, "completion_tokens", 0) or 0,
        "cost": _cost(r),
    }
    return parse_json(r.choices[0].message.content or ""), usage


def chat_text(system: str, user: str, model: str, max_tokens: int = 200):
    """Plain-text completion (used for chunk contextualisation). Returns (text, usage)."""
    r = _complete(
        model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0,
        max_tokens=max_tokens,
    )
    u = getattr(r, "usage", None)
    usage = {"prompt": getattr(u, "prompt_tokens", 0) or 0, "completion": getattr(u, "completion_tokens", 0) or 0, "cost": _cost(r)}
    return (r.choices[0].message.content or "").strip(), usage


def plain_answer(question: str, class_level: int, model: str, max_tokens: int = 700):
    """Baseline for eval: same LLM, NO retrieval."""
    r = _complete(
        model,
        messages=[
            {"role": "system", "content": f"Answer in simple Bangla for a class {class_level} student in Bangladesh. Be concise."},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=max_tokens,
    )
    u = getattr(r, "usage", None)
    usage = {"prompt": getattr(u, "prompt_tokens", 0) or 0, "completion": getattr(u, "completion_tokens", 0) or 0, "cost": _cost(r)}
    return r.choices[0].message.content or "", usage


def chat_image_json(system: str, image_base64: str, mime_type: str, model: str, max_tokens: int = 500):
    """Sends image to multimodal LLM to transcribe question text. Returns (obj, usage)."""
    litellm = _litellm()

    image_url = f"data:{mime_type};base64,{image_base64}"
    r = litellm.completion(
        model=model,
        timeout=20,
        num_retries=0,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe the question from this textbook image:"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
        temperature=0,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    u = getattr(r, "usage", None)
    usage = {
        "prompt": getattr(u, "prompt_tokens", 0) or 0,
        "completion": getattr(u, "completion_tokens", 0) or 0,
        "cost": _cost(r),
    }
    return parse_json(r.choices[0].message.content or ""), usage
