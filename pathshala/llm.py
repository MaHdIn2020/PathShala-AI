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


def chat_json(system: str, user: str, model: str, max_tokens: int = 1500):
    """Returns (obj, usage). obj={} if model output was not valid JSON."""
    litellm = _litellm()

    r = litellm.completion(
        model=model,
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
    litellm = _litellm()

    r = litellm.completion(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0,
        max_tokens=max_tokens,
    )
    u = getattr(r, "usage", None)
    usage = {"prompt": getattr(u, "prompt_tokens", 0) or 0, "completion": getattr(u, "completion_tokens", 0) or 0, "cost": _cost(r)}
    return (r.choices[0].message.content or "").strip(), usage


def plain_answer(question: str, class_level: int, model: str, max_tokens: int = 700):
    """Baseline for eval: same LLM, NO retrieval."""
    litellm = _litellm()

    r = litellm.completion(
        model=model,
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
