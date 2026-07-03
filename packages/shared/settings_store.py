"""Runtime settings – DB overrides .env, editable via dashboard GUI."""

from __future__ import annotations

import json
import os
from typing import Any

from packages.shared.config import settings
from packages.shared.db import get_connection

# Maps DB key → Settings/env attribute name
SETTING_FIELDS: dict[str, dict[str, Any]] = {
    "llm_provider":          {"group": "llm", "label": "LLM Provider", "type": "select", "options": ["groq", "anthropic"], "secret": False},
    "groq_api_key":            {"group": "llm", "label": "Groq API Key", "type": "password", "secret": True},
    "anthropic_api_key":       {"group": "llm", "label": "Anthropic API Key", "type": "password", "secret": True},
    "default_llm_model":       {"group": "llm", "label": "Default Model", "type": "text", "secret": False},
    "classifier_model":        {"group": "llm", "label": "Classifier Model", "type": "text", "secret": False},
    "brevo_api_key":           {"group": "email", "label": "Brevo API Key", "type": "password", "secret": True},
    "outbound_from_email":     {"group": "email", "label": "From Email", "type": "email", "secret": False},
    "outbound_from_name":      {"group": "email", "label": "From Name", "type": "text", "secret": False},
    "daily_email_limit":       {"group": "email", "label": "Daily Email Limit", "type": "number", "secret": False},
    "api_domain":              {"group": "domains", "label": "API Domain", "type": "text", "secret": False},
    "landing_domain":          {"group": "domains", "label": "Landing Domain", "type": "text", "secret": False},
    "dashboard_domain":        {"group": "domains", "label": "Dashboard Domain", "type": "text", "secret": False},
    "n8n_host":                {"group": "domains", "label": "n8n Domain", "type": "text", "secret": False},
    "n8n_webhook_url":         {"group": "domains", "label": "n8n Webhook URL", "type": "text", "secret": False},
    "affiliate_product_slug":  {"group": "affiliate", "label": "Product Slug", "type": "text", "secret": False},
    "affiliate_tracking_base": {"group": "affiliate", "label": "Affiliate Link", "type": "url", "secret": False},
    "affiliate_postback_secret": {"group": "affiliate", "label": "Postback Secret", "type": "password", "secret": True},
    "icp_industry":            {"group": "agent", "label": "ICP Industry", "type": "text", "secret": False},
    "icp_min_employees":       {"group": "agent", "label": "Min Employees", "type": "number", "secret": False},
    "icp_max_employees":       {"group": "agent", "label": "Max Employees", "type": "number", "secret": False},
    "lead_score_threshold":    {"group": "agent", "label": "Score Threshold", "type": "number", "secret": False},
    "settings_pin":            {"group": "security", "label": "Settings PIN", "type": "password", "secret": True},
}

ENV_MAP = {
    "llm_provider": "LLM_PROVIDER",
    "groq_api_key": "GROQ_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "default_llm_model": "DEFAULT_LLM_MODEL",
    "classifier_model": "CLASSIFIER_MODEL",
    "brevo_api_key": "BREVO_API_KEY",
    "outbound_from_email": "OUTBOUND_FROM_EMAIL",
    "outbound_from_name": "OUTBOUND_FROM_NAME",
    "daily_email_limit": "DAILY_EMAIL_LIMIT",
    "api_domain": "API_DOMAIN",
    "landing_domain": "LANDING_DOMAIN",
    "dashboard_domain": "DASHBOARD_DOMAIN",
    "n8n_host": "N8N_HOST",
    "n8n_webhook_url": "N8N_WEBHOOK_URL",
    "affiliate_product_slug": "AFFILIATE_PRODUCT_SLUG",
    "affiliate_tracking_base": "AFFILIATE_TRACKING_BASE",
    "affiliate_postback_secret": "AFFILIATE_POSTBACK_SECRET",
    "icp_industry": "ICP_INDUSTRY",
    "icp_min_employees": "ICP_MIN_EMPLOYEES",
    "icp_max_employees": "ICP_MAX_EMPLOYEES",
    "lead_score_threshold": "LEAD_SCORE_THRESHOLD",
}

SETTINGS_ATTR = {
    "llm_provider": "llm_provider",
    "groq_api_key": "groq_api_key",
    "anthropic_api_key": "anthropic_api_key",
    "default_llm_model": "default_llm_model",
    "classifier_model": "classifier_model",
    "brevo_api_key": "brevo_api_key",
    "outbound_from_email": "outbound_from_email",
    "outbound_from_name": "outbound_from_name",
    "daily_email_limit": "daily_email_limit",
    "affiliate_product_slug": "affiliate_product_slug",
    "affiliate_tracking_base": "affiliate_tracking_base",
    "affiliate_postback_secret": "affiliate_postback_secret",
    "icp_industry": "icp_industry",
    "icp_min_employees": "icp_min_employees",
    "icp_max_employees": "icp_max_employees",
    "lead_score_threshold": "lead_score_threshold",
}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return value[:4] + "••••" + value[-4:]


def _env_fallback(key: str) -> str:
    env_name = ENV_MAP.get(key)
    if env_name:
        val = os.getenv(env_name, "")
        if val:
            return val
    attr = SETTINGS_ATTR.get(key)
    if attr:
        return str(getattr(settings, attr, "") or "")
    pydantic_map = {
        "api_domain": "api_domain",
        "landing_domain": "landing_domain",
        "dashboard_domain": "dashboard_domain",
        "n8n_host": "n8n_host",
        "n8n_webhook_url": "n8n_webhook_base",
    }
    if key in pydantic_map and hasattr(settings, pydantic_map[key]):
        return str(getattr(settings, pydantic_map[key], "") or "")
    return ""


async def get_runtime(key: str) -> str:
    """DB value first, then .env fallback."""
    try:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT value FROM app_settings WHERE key = $1", key)
            if row and row["value"]:
                return row["value"]
    except Exception:
        pass
    return _env_fallback(key)


async def get_all_masked() -> dict:
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT key, value, is_secret FROM app_settings ORDER BY key")
    db_vals = {r["key"]: r["value"] for r in rows}
    result: dict[str, Any] = {"groups": {}, "configured": {}}

    for key, meta in SETTING_FIELDS.items():
        raw = db_vals.get(key) or _env_fallback(key)
        is_secret = meta.get("secret", False)
        display = _mask(raw) if is_secret and raw else raw
        configured = bool(raw and raw not in ("", "change-me-postback-secret", "generate-a-random-32-character-key"))

        group = meta["group"]
        result["groups"].setdefault(group, []).append({
            "key": key,
            "label": meta["label"],
            "type": meta["type"],
            "value": display,
            "configured": configured,
            "options": meta.get("options"),
        })
        result["configured"][key] = configured

    return result


async def save_settings(updates: dict[str, str], pin: str | None = None) -> dict:
    stored_pin = await get_runtime("settings_pin")
    if stored_pin and pin != stored_pin:
        raise PermissionError("Invalid settings PIN")

    saved = []
    async with get_connection() as conn:
        for key, value in updates.items():
            if key not in SETTING_FIELDS:
                continue
            if value == "__UNCHANGED__":
                continue
            is_secret = SETTING_FIELDS[key].get("secret", False)
            await conn.execute(
                """INSERT INTO app_settings (key, value, is_secret, updated_at)
                   VALUES ($1, $2, $3, now())
                   ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()""",
                key, value.strip(), is_secret,
            )
            saved.append(key)

    return {"saved": saved, "count": len(saved)}


async def export_env_file() -> str:
    lines = ["# Auto-generated from dashboard settings", ""]
    for key, env_name in ENV_MAP.items():
        val = await get_runtime(key)
        if val:
            lines.append(f"{env_name}={val}")
    domain_keys = [
        ("api_domain", "API_DOMAIN"),
        ("landing_domain", "LANDING_DOMAIN"),
        ("dashboard_domain", "DASHBOARD_DOMAIN"),
        ("n8n_host", "N8N_HOST"),
        ("n8n_webhook_url", "N8N_WEBHOOK_URL"),
    ]
    for key, env_name in domain_keys:
        val = await get_runtime(key)
        if val:
            lines.append(f"{env_name}={val}")
    return "\n".join(lines) + "\n"


async def test_connections() -> dict:
    results: dict[str, Any] = {}

    provider = await get_runtime("llm_provider") or "groq"
    if provider == "groq":
        key = await get_runtime("groq_api_key")
        if not key:
            results["groq"] = {"ok": False, "message": "No API key"}
        else:
            try:
                from groq import Groq
                client = Groq(api_key=key)
                client.chat.completions.create(
                    model=await get_runtime("classifier_model") or "llama-3.1-8b-instant",
                    max_tokens=5,
                    messages=[{"role": "user", "content": "ping"}],
                )
                results["groq"] = {"ok": True, "message": "Connected"}
            except Exception as exc:
                results["groq"] = {"ok": False, "message": str(exc)[:120]}
    else:
        key = await get_runtime("anthropic_api_key")
        results["anthropic"] = {"ok": bool(key), "message": "Key set" if key else "No API key"}

    brevo_key = await get_runtime("brevo_api_key")
    if not brevo_key:
        results["brevo"] = {"ok": False, "message": "No API key"}
    else:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.brevo.com/v3/account",
                    headers={"api-key": brevo_key},
                )
            results["brevo"] = {"ok": resp.status_code == 200, "message": "Connected" if resp.status_code == 200 else resp.text[:80]}
        except Exception as exc:
            results["brevo"] = {"ok": False, "message": str(exc)[:120]}

    results["domains"] = {
        "api": await get_runtime("api_domain"),
        "landing": await get_runtime("landing_domain"),
        "dashboard": await get_runtime("dashboard_domain"),
        "n8n": await get_runtime("n8n_host"),
    }
    return results
