import json
import os

import httpx


class AIError(Exception):
    """Any reason the suggestion is unavailable: no key, rate limit, network, bad reply."""


def suggest_substitutes(name: str, avoid: list[str]) -> list[str]:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise AIError("GEMINI_API_KEY is not set")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    prompt = (
        f"Gợi ý tối đa 3 nguyên liệu rẻ, dễ mua ở siêu thị Việt Nam để thay thế '{name}' khi nấu ăn. "
        f"Không dùng: {', '.join(avoid) or 'không có'}. "
        "Chỉ trả về một mảng JSON các tên ngắn bằng tiếng Việt."
    )
    try:
        reply = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key},  # header, never in the URL, so logs stay clean
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=10,
        )
        reply.raise_for_status()
        names = json.loads(reply.json()["candidates"][0]["content"]["parts"][0]["text"])
        # The model can ignore the "do not use" list, so check it in code too.
        return [n for n in names if isinstance(n, str) and not any(w in n.lower() for w in avoid)][:3]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise AIError(type(exc).__name__) from exc
