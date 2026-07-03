"""Database access layer."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import asyncpg

from packages.shared.config import settings


@asynccontextmanager
async def get_connection():
    conn = await asyncpg.connect(settings.database_url)
    try:
        yield conn
    finally:
        await conn.close()


async def upsert_lead(lead: dict[str, Any]) -> UUID:
    query = """
        INSERT INTO leads (
            email, first_name, last_name, company, job_title, phone,
            linkedin_url, website, industry, employee_count, country,
            source, utm_source, utm_campaign, metadata
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb)
        ON CONFLICT (email) DO UPDATE SET
            first_name = COALESCE(EXCLUDED.first_name, leads.first_name),
            last_name = COALESCE(EXCLUDED.last_name, leads.last_name),
            company = COALESCE(EXCLUDED.company, leads.company),
            updated_at = now()
        RETURNING id
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            query,
            lead["email"],
            lead.get("first_name"),
            lead.get("last_name"),
            lead.get("company"),
            lead.get("job_title"),
            lead.get("phone"),
            lead.get("linkedin_url"),
            lead.get("website"),
            lead.get("industry"),
            lead.get("employee_count"),
            lead.get("country", "DE"),
            lead.get("source"),
            lead.get("utm_source"),
            lead.get("utm_campaign"),
            json.dumps(lead.get("metadata", {})),
        )
        return row["id"]


async def update_lead_score(lead_id: UUID, score: int, icp_match: bool, status: str | None = None) -> None:
    async with get_connection() as conn:
        if status:
            await conn.execute(
                "UPDATE leads SET score = $2, icp_match = $3, status = $4::lead_status, updated_at = now() WHERE id = $1",
                lead_id, score, icp_match, status,
            )
        else:
            await conn.execute(
                "UPDATE leads SET score = $2, icp_match = $3, updated_at = now() WHERE id = $1",
                lead_id, score, icp_match,
            )


async def log_interaction(
    lead_id: UUID,
    channel: str,
    direction: str,
    body: str,
    *,
    subject: str | None = None,
    summary: str | None = None,
    sentiment: str | None = None,
    agent_name: str | None = None,
    metadata: dict | None = None,
) -> UUID:
    query = """
        INSERT INTO interactions (
            lead_id, channel, direction, subject, body, summary,
            sentiment, agent_name, metadata
        ) VALUES ($1, $2::interaction_channel, $3::interaction_direction,
                  $4, $5, $6, $7, $8, $9::jsonb)
        RETURNING id
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            query, lead_id, channel, direction, subject, body,
            summary, sentiment, agent_name, json.dumps(metadata or {}),
        )
        return row["id"]


async def log_agent_run(
    agent_name: str,
    *,
    lead_id: UUID | None = None,
    input_summary: str | None = None,
    output_summary: str | None = None,
    status: str = "success",
    error_message: str | None = None,
    duration_ms: int | None = None,
    metadata: dict | None = None,
) -> UUID:
    query = """
        INSERT INTO agent_runs (
            agent_name, lead_id, input_summary, output_summary,
            status, error_message, duration_ms, metadata, finished_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, now())
        RETURNING id
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            query, agent_name, lead_id, input_summary, output_summary,
            status, error_message, duration_ms, json.dumps(metadata or {}),
        )
        return row["id"]


async def get_lead_by_email(email: str) -> asyncpg.Record | None:
    async with get_connection() as conn:
        return await conn.fetchrow("SELECT * FROM leads WHERE email = $1", email)


async def get_lead_by_id(lead_id: UUID) -> asyncpg.Record | None:
    async with get_connection() as conn:
        return await conn.fetchrow("SELECT * FROM leads WHERE id = $1", lead_id)


async def get_sequence_step(sequence_slug: str, step_order: int) -> asyncpg.Record | None:
    async with get_connection() as conn:
        return await conn.fetchrow(
            """SELECT s.* FROM email_sequence_steps s
               JOIN email_sequences e ON e.id = s.sequence_id
               WHERE e.slug = $1 AND s.step_order = $2 AND e.is_active = true""",
            sequence_slug, step_order,
        )


async def get_sequence_state(lead_id: UUID, sequence_slug: str) -> asyncpg.Record | None:
    async with get_connection() as conn:
        return await conn.fetchrow(
            """SELECT lss.* FROM lead_sequence_state lss
               JOIN email_sequences e ON e.id = lss.sequence_id
               WHERE lss.lead_id = $1 AND e.slug = $2""",
            lead_id, sequence_slug,
        )


async def upsert_sequence_state(
    lead_id: UUID,
    sequence_slug: str,
    current_step: int,
    delay_days: int,
) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """INSERT INTO lead_sequence_state (lead_id, sequence_id, current_step, next_send_at)
               SELECT $1, e.id, $2,
                      CASE WHEN $3 > 0 THEN now() + ($3 || ' days')::interval ELSE NULL END
               FROM email_sequences e WHERE e.slug = $4
               ON CONFLICT (lead_id, sequence_id) DO UPDATE SET
                   current_step = EXCLUDED.current_step,
                   next_send_at = EXCLUDED.next_send_at,
                   completed = false""",
            lead_id, current_step, delay_days, sequence_slug,
        )


async def mark_sequence_completed(lead_id: UUID, sequence_slug: str) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """UPDATE lead_sequence_state lss SET completed = true, next_send_at = NULL
               FROM email_sequences e
               WHERE lss.sequence_id = e.id AND lss.lead_id = $1 AND e.slug = $2""",
            lead_id, sequence_slug,
        )


async def get_due_followups(limit: int) -> list[asyncpg.Record]:
    async with get_connection() as conn:
        return await conn.fetch(
            """SELECT lss.*, e.slug AS sequence_slug, l.email, l.first_name, l.do_not_contact
               FROM lead_sequence_state lss
               JOIN email_sequences e ON e.id = lss.sequence_id
               JOIN leads l ON l.id = lss.lead_id
               WHERE lss.completed = false AND lss.paused = false
                 AND lss.next_send_at IS NOT NULL AND lss.next_send_at <= now()
                 AND l.do_not_contact = false
               ORDER BY lss.next_send_at
               LIMIT $1""",
            limit,
        )

