"""Ensure optional DB tables exist (safe on every API start)."""

from __future__ import annotations

from packages.shared.db import get_connection
from packages.shared.settings_store import SETTING_FIELDS


async def ensure_app_schema() -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
              key         TEXT PRIMARY KEY,
              value       TEXT NOT NULL DEFAULT '',
              is_secret   BOOLEAN NOT NULL DEFAULT false,
              updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        for key, meta in SETTING_FIELDS.items():
            await conn.execute(
                """
                INSERT INTO app_settings (key, is_secret)
                VALUES ($1, $2)
                ON CONFLICT (key) DO NOTHING
                """,
                key,
                meta.get("secret", False),
            )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operator_profile (
              id            INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
              display_name  TEXT NOT NULL DEFAULT 'Agent Commander',
              xp_total      INT NOT NULL DEFAULT 0,
              streak_days   INT NOT NULL DEFAULT 0,
              last_active   DATE,
              created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute("INSERT INTO operator_profile (id) VALUES (1) ON CONFLICT (id) DO NOTHING")

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS xp_events (
              id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              event_type  TEXT NOT NULL,
              xp_amount   INT NOT NULL,
              description TEXT,
              metadata    JSONB NOT NULL DEFAULT '{}',
              created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
