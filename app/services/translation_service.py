import json
import re

import httpx

from app.config import settings


def _deepl_lang(code: str) -> str:
    """Normalize BCP-47 language codes to DeepL format (uppercase, hyphen-separated)."""
    # DeepL expects e.g. EN, DE, ZH-HANS, PT-BR
    return code.upper().replace("_", "-")


async def translate_with_deepl(source_lang: str, target_lang: str, texts: list[str]) -> list[str]:
    key = settings.deepl_api_key
    if not key:
        raise RuntimeError("DEEPL_NOT_CONFIGURED")

    src = _deepl_lang(source_lang)
    tgt = _deepl_lang(target_lang)
    results: list[str] = []

    async with httpx.AsyncClient(timeout=30) as client:
        # DeepL accepts up to 50 texts per request
        for i in range(0, len(texts), 50):
            batch = texts[i : i + 50]
            resp = await client.post(
                "https://api-free.deepl.com/v2/translate",
                headers={"DeepL-Auth-Key": key.get_secret_value()},
                json={"text": batch, "source_lang": src, "target_lang": tgt},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"DEEPL_ERROR: {resp.status_code}")
            data = resp.json()
            results.extend(t["text"] for t in data["translations"])

    return results


async def translate_with_llm(source_lang: str, target_lang: str, texts: list[str]) -> list[str]:
    key = settings.llm_api_key
    if not key:
        raise RuntimeError("LLM_NOT_CONFIGURED")

    # Send texts as a JSON array; ask LLM to return a same-length JSON array
    payload = json.dumps(texts, ensure_ascii=False)
    system_prompt = (
        f"You are a professional app localizer. Translate the following JSON array of UI strings "
        f"from '{source_lang}' to '{target_lang}'. "
        "Return a JSON array of the same length with translated strings in the same order. "
        "Return only valid JSON, no explanation."
    )

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.llm_api_base}/chat/completions",
            headers={"Authorization": f"Bearer {key.get_secret_value()}"},
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": payload},
                ],
                "temperature": 0.2,
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(f"LLM_ERROR: {resp.status_code}")

    content = resp.json()["choices"][0]["message"]["content"].strip()
    # Strip markdown code fences if present
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.MULTILINE).strip()

    try:
        translated = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM_ERROR: malformed JSON response: {e}") from e

    if not isinstance(translated, list) or len(translated) != len(texts):
        raise RuntimeError(f"LLM_ERROR: expected list of {len(texts)} items, got {translated!r:.200}")

    return [str(t) for t in translated]


async def prefill(source_lang: str, target_lang: str, texts: list[str], provider: str) -> list[str]:
    if provider == "deepl":
        return await translate_with_deepl(source_lang, target_lang, texts)
    elif provider == "llm":
        return await translate_with_llm(source_lang, target_lang, texts)
    else:
        raise ValueError(f"Unknown provider: {provider}")
