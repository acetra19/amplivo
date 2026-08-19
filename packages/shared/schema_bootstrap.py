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

        # Amplivo Clips subsidiary
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clip_campaigns (
              id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              marketplace     TEXT NOT NULL DEFAULT 'manual',
              external_id     TEXT,
              title           TEXT NOT NULL,
              source_url      TEXT NOT NULL,
              brief           TEXT,
              payout_model    TEXT NOT NULL DEFAULT 'cpm',
              payout_rate     NUMERIC(10,4),
              currency        TEXT NOT NULL DEFAULT 'USD',
              status          TEXT NOT NULL DEFAULT 'open',
              metadata        JSONB NOT NULL DEFAULT '{}',
              created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_clip_campaigns_marketplace_ext
            ON clip_campaigns (marketplace, external_id)
            WHERE external_id IS NOT NULL
            """
        )
        # Ensure ON CONFLICT target exists even if an older bootstrap omitted the index.
        await conn.execute(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_clip_campaigns_marketplace_ext'
              ) THEN
                CREATE UNIQUE INDEX idx_clip_campaigns_marketplace_ext
                ON clip_campaigns (marketplace, external_id)
                WHERE external_id IS NOT NULL;
              END IF;
            END $$;
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clip_jobs (
              id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              campaign_id     UUID NOT NULL REFERENCES clip_campaigns(id) ON DELETE CASCADE,
              status          TEXT NOT NULL DEFAULT 'queued',
              opus_project_id TEXT,
              clip_url        TEXT,
              post_url        TEXT,
              proof_url       TEXT,
              qa_score        INT,
              qa_notes        TEXT,
              error_message   TEXT,
              payout_amount   NUMERIC(10,2),
              metadata        JSONB NOT NULL DEFAULT '{}',
              created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_clip_jobs_status ON clip_jobs(status)"
        )

        # Refresh Systeme.io sequence CTAs when steps table exists.
        exists = await conn.fetchval(
            """SELECT EXISTS (
                 SELECT 1 FROM information_schema.tables
                 WHERE table_name = 'email_sequence_steps'
               )"""
        )
        if exists:
            # Revenue sprint CTAs (idempotent full replace of Systeme sequences).
            await conn.execute(
                """
                UPDATE email_sequence_steps AS s
                SET
                  subject_tpl = v.subject_tpl,
                  body_tpl = v.body_tpl
                FROM email_sequences AS es,
                LATERAL (VALUES
                  (1, 'Kurze Frage zu {{company}}',
                   E'Hallo {{first_name}},\n\nkurz zu {{company}}: womit baust du aktuell Funnels, E-Mail und Kurszugang – ein Tool oder mehrere?\n\nIch frage, weil Solo-Setups dort oft unnötig Zeit verlieren. Kein Pitch, nur die eine Frage.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Kein Interesse? Antworte STOP.'),
                  (2, 'Re: Kurze Frage zu {{company}}',
                   E'Hallo {{first_name}},\n\nkurz nachgehakt.\n\nAngebot: Ich richte dir in 20 Minuten den kostenlosen Systeme.io-Account + einen ersten Funnel ein (ohne Kreditkarte).\n\n1) Free-Zugang hier anlegen:\n{{affiliate_url}}\n2) Antworte mit SETUP – dann machen wir den Rest gemeinsam per Mail.\n\nWenn es nicht passt: ignorieren oder STOP.\n\nBeste Gruesse\n{{sender_name}}'),
                  (3, 'Letzte Nachricht – Setup-Hilfe {{company}}',
                   E'Hallo {{first_name}},\n\nletzte Mail von mir.\n\nFalls Stack gerade Thema ist: Free-Account + 20-Min Setup-Hilfe von mir.\nZugang:\n{{affiliate_url}}\n\nAntworte SETUP wenn du willst – sonst alles gut.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. STOP zum Abmelden.')
                ) AS v(step_order, subject_tpl, body_tpl)
                WHERE s.sequence_id = es.id
                  AND es.slug = 'outbound_a'
                  AND s.step_order = v.step_order
                """
            )
            await conn.execute(
                """
                UPDATE email_sequence_steps AS s
                SET
                  subject_tpl = v.subject_tpl,
                  body_tpl = v.body_tpl
                FROM email_sequences AS es,
                LATERAL (VALUES
                  (1, 'Kurze Frage an {{company}}',
                   E'Hallo {{first_name}},\n\nbei {{company}}: laeuft Funnel + E-Mail + Kurs schon in einem System – oder noch getrennt?\n\nNur diese eine Frage.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Antworte STOP zum Abmelden.'),
                  (2, 'Re: Tool-Setup {{company}}',
                   E'Hallo {{first_name}},\n\nkurz der Reminder.\n\nWenn getrennte Tools nerven: Free-Plan Systeme.io + ich helfe 20 Min beim ersten Funnel.\n{{affiliate_url}}\n\nAntworte SETUP – sonst einfach ignorieren.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. STOP zum Abmelden.')
                ) AS v(step_order, subject_tpl, body_tpl)
                WHERE s.sequence_id = es.id
                  AND es.slug = 'nurture_b'
                  AND s.step_order = v.step_order
                """
            )
