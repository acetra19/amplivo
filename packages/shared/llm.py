"""LLM utilities – supports Groq (default, cheap) and Anthropic."""

from __future__ import annotations

import json
import re

from packages.shared.config import settings
from packages.shared.settings_store import get_runtime


def extract_json(text: str) -> dict:
    """Extract JSON object from LLM response, handling markdown fences."""
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    return json.loads(cleaned)


async def _chat(system: str, prompt: str, model: str, max_tokens: int) -> str:
    provider = (await get_runtime("llm_provider") or settings.llm_provider).lower()

    if provider == "groq":
        api_key = await get_runtime("groq_api_key")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not configured – set it in Dashboard → Settings")
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""

    if provider == "anthropic":
        api_key = await get_runtime("anthropic_api_key")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured – set it in Dashboard → Settings")
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


async def classify_text(prompt: str, system: str, model: str | None = None) -> str:
    m = model or await get_runtime("classifier_model") or settings.classifier_model
    return await _chat(system, prompt, m, max_tokens=1024)


async def generate_text(prompt: str, system: str, model: str | None = None) -> str:
    m = model or await get_runtime("default_llm_model") or settings.default_llm_model
    return await _chat(system, prompt, m, max_tokens=2048)
