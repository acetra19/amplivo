#!/usr/bin/env python3
"""Validate project setup before deploy (no secrets required for structure check)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "Dockerfile",
    "database/schema.sql",
    "database/03-knowledge-seed.sql",
    "database/06-systeme-knowledge-seed.sql",
    "landing/index.html",
    "packages/api/main.py",
    "scripts/deploy-vps.sh",
    "infra/Caddyfile",
]

REQUIRED_WORKFLOWS = [
    "new-lead.json",
    "email-reply.json",
    "email-followup-daily.json",
    "trial-started.json",
    "daily-ops-report.json",
]

ENV_REQUIRED_FOR_DEPLOY = [
    "POSTGRES_PASSWORD",
    "N8N_ENCRYPTION_KEY",
    "API_DOMAIN",
    "N8N_HOST",
    "N8N_WEBHOOK_URL",
    "BREVO_API_KEY",
    "OUTBOUND_FROM_EMAIL",
    "AFFILIATE_POSTBACK_SECRET",
]


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED_FILES:
        if not (ROOT / rel).is_file():
            errors.append(f"Missing file: {rel}")

    wf_dir = ROOT / "n8n" / "workflows"
    for wf in REQUIRED_WORKFLOWS:
        if not (wf_dir / wf).is_file():
            errors.append(f"Missing workflow: n8n/workflows/{wf}")

    env_path = ROOT / ".env"
    if not env_path.is_file():
        warnings.append(".env not found – copy from .env.example")
    else:
        env = _load_env(env_path)
        for key in ENV_REQUIRED_FOR_DEPLOY:
            if not env.get(key):
                warnings.append(f".env: {key} not set")

        if not env.get("AFFILIATE_TRACKING_BASE"):
            warnings.append("AFFILIATE_TRACKING_BASE not set in .env")
        if env.get("AFFILIATE_PRODUCT_SLUG", "gohighlevel") == "gohighlevel" and not env.get("AFFILIATE_TRACKING_BASE"):
            warnings.append("Consider AFFILIATE_PRODUCT_SLUG=systeme-io with your Systeme.io link")

        provider = env.get("LLM_PROVIDER", "groq").lower()
        if provider == "groq" and not env.get("GROQ_API_KEY"):
            warnings.append(".env: GROQ_API_KEY not set (get free key at console.groq.com)")
        if provider == "anthropic" and not env.get("ANTHROPIC_API_KEY"):
            warnings.append(".env: ANTHROPIC_API_KEY not set")

    print("Agentur setup check\n" + "=" * 40)
    if errors:
        print("\nERRORS:")
        for e in errors:
            print(f"  x {e}")

    if warnings:
        print("\nWARNINGS (fill before go-live):")
        for w in warnings:
            print(f"  ! {w}")

    if not errors and not warnings:
        print("\nAll checks passed. Ready to deploy.")
    elif not errors:
        print("\nStructure OK. Complete .env warnings before production.")
    else:
        print("\nFix errors before deploying.")
        return 1

    return 0


def _load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        result[key.strip()] = val.strip()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
