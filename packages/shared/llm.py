"""LLM utilities – supports Groq (default, cheap) and Anthropic."""

from __future__ import annotations

import json
import re

from packages.shared.config import settings
from packages.shared.settings_store import get_runtime

# Groq shut down these IDs on 2026-08-16 — remap legacy runtime/env values.
GROQ_MODEL_ALIASES = {
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.3-70b-specdec": "openai/gpt-oss-120b",
    "llama3-70b-8192": "openai/gpt-oss-120b",
    "llama3-8b-8192": "openai/gpt-oss-20b",
    "mixtral-8x7b-32768": "openai/gpt-oss-120b",
    "gemma2-9b-it": "openai/gpt-oss-20b",
}


def resolve_model(model: str) -> str:
    return GROQ_MODEL_ALIASES.get(model, model)


def extract_json(text: str) -> dict:
    """Extract JSON object from LLM response, handling markdown fences."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise json.JSONDecodeError("empty LLM response", cleaned, 0)
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Model often wraps JSON in prose — pull the first object
        obj_match = re.search(r"\{[\s\S]*\}", cleaned)
        if not obj_match:
            raise
        return json.loads(obj_match.group(0))


async def _chat(system: str, prompt: str, model: str, max_tokens: int) -> str:
    provider = (await get_runtime("llm_provider") or settings.llm_provider).lower()
    model = resolve_model(model)

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
