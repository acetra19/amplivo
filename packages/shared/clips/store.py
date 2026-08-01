"""DB access for Amplivo Clips campaigns and jobs."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from packages.shared.db import get_connection

# Jobs that block a new produce cycle for the same campaign.
ACTIVE_JOB_STATUSES = (
    "queued",
    "producing",
    "qa",
    "ready",
    "posted",
    "submitted",
    "paid",
)


async def create_campaign(data: dict[str, Any]) -> UUID:
    external_id = data.get("external_id") or f"manual-{uuid4().hex[:12]}"
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO clip_campaigns (
              marketplace, external_id, title, source_url, brief,
              payout_model, payout_rate, currency, metadata
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)
            ON CONFLICT (marketplace, external_id) WHERE external_id IS NOT NULL
            DO UPDATE SET
              title = EXCLUDED.title,
              source_url = EXCLUDED.source_url,
              brief = EXCLUDED.brief,
              payout_rate = EXCLUDED.payout_rate,
              updated_at = now()
            RETURNING id
            """,
            data.get("marketplace") or "manual",
            external_id,
            data["title"],
            data["source_url"],
            data.get("brief"),
            data.get("payout_model") or "cpm",
            data.get("payout_rate"),
            data.get("currency") or "USD",
            json.dumps(data.get("metadata") or {}),
        )
        return row["id"]


async def list_open_campaigns(limit: int = 20) -> list:
    async with get_connection() as conn:
        return await conn.fetch(
            """
            SELECT * FROM clip_campaigns
            WHERE status = 'open'
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )


async def list_workable_campaigns(limit: int = 20) -> list:
    """Open campaigns with no blocking job (prevents drain runaway)."""
    async with get_connection() as conn:
        return await conn.fetch(
            """
            SELECT c.*
            FROM clip_campaigns c
            WHERE c.status = 'open'
              AND NOT EXISTS (
                SELECT 1 FROM clip_jobs j
                WHERE j.campaign_id = c.id
                  AND j.status = ANY($2::text[])
              )
            ORDER BY c.created_at ASC
            LIMIT $1
            """,
            limit,
            list(ACTIVE_JOB_STATUSES),
        )


async def list_campaigns(limit: int = 50, status: str | None = None) -> list:
    async with get_connection() as conn:
        if status:
            return await conn.fetch(
                """
                SELECT * FROM clip_campaigns
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                status,
                limit,
            )
        return await conn.fetch(
            """
            SELECT * FROM clip_campaigns
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )


async def set_campaign_status(campaign_id: UUID, status: str) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE clip_campaigns
            SET status = $2, updated_at = now()
            WHERE id = $1
            """,
            campaign_id,
            status,
        )


async def list_jobs_by_status(status: str, limit: int = 20) -> list:
    async with get_connection() as conn:
        return await conn.fetch(
            """
            SELECT j.*, c.title AS campaign_title, c.marketplace, c.source_url,
                   c.brief, c.payout_rate, c.currency
            FROM clip_jobs j
            JOIN clip_campaigns c ON c.id = j.campaign_id
            WHERE j.status = $1
            ORDER BY j.created_at DESC
            LIMIT $2
            """,
            status,
            limit,
        )


async def list_producing_jobs(limit: int = 20) -> list:
    return await list_jobs_by_status("producing", limit=limit)


async def get_campaign(campaign_id: UUID):
    async with get_connection() as conn:
        return await conn.fetchrow("SELECT * FROM clip_campaigns WHERE id = $1", campaign_id)


async def campaign_has_blocking_job(campaign_id: UUID) -> bool:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 AS ok FROM clip_jobs
            WHERE campaign_id = $1 AND status = ANY($2::text[])
            LIMIT 1
            """,
            campaign_id,
            list(ACTIVE_JOB_STATUSES),
        )
        return bool(row)


async def create_job(campaign_id: UUID) -> UUID:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO clip_jobs (campaign_id, status)
            VALUES ($1, 'queued')
            RETURNING id
            """,
            campaign_id,
        )
        return row["id"]


async def update_job(job_id: UUID, **fields: Any) -> None:
    if not fields:
        return
    cols = []
    vals: list[Any] = [job_id]
    idx = 2
    for key, value in fields.items():
        if key == "metadata":
            cols.append(f"metadata = ${idx}::jsonb")
            vals.append(json.dumps(value))
        else:
            cols.append(f"{key} = ${idx}")
            vals.append(value)
        idx += 1
    cols.append("updated_at = now()")
    async with get_connection() as conn:
        await conn.execute(
            f"UPDATE clip_jobs SET {', '.join(cols)} WHERE id = $1",
            *vals,
        )


async def get_job(job_id: UUID):
    async with get_connection() as conn:
        return await conn.fetchrow(
            """
            SELECT j.*, c.title AS campaign_title, c.source_url, c.marketplace,
                   c.brief, c.payout_rate, c.currency
            FROM clip_jobs j
            JOIN clip_campaigns c ON c.id = j.campaign_id
            WHERE j.id = $1
            """,
            job_id,
        )


async def list_jobs(limit: int = 30) -> list:
    async with get_connection() as conn:
        return await conn.fetch(
            """
            SELECT j.id, j.status, j.qa_score, j.qa_notes, j.clip_url, j.post_url,
                   j.proof_url, j.error_message, j.payout_amount, j.created_at,
                   c.title AS campaign_title, c.marketplace, c.currency
            FROM clip_jobs j
            JOIN clip_campaigns c ON c.id = j.campaign_id
            ORDER BY j.created_at DESC
            LIMIT $1
            """,
            limit,
        )


async def clip_stats() -> dict:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
              (SELECT COUNT(*)::int FROM clip_campaigns WHERE status = 'open') AS open_campaigns,
              (SELECT COUNT(*)::int FROM clip_campaigns) AS total_campaigns,
              (SELECT COUNT(*)::int FROM clip_jobs) AS total_jobs,
              (SELECT COUNT(*)::int FROM clip_jobs WHERE status = 'queued') AS queued,
              (SELECT COUNT(*)::int FROM clip_jobs WHERE status = 'producing') AS producing,
              (SELECT COUNT(*)::int FROM clip_jobs WHERE status = 'qa') AS qa,
              (SELECT COUNT(*)::int FROM clip_jobs WHERE status = 'ready') AS ready,
              (SELECT COUNT(*)::int FROM clip_jobs WHERE status = 'submitted') AS submitted,
              (SELECT COUNT(*)::int FROM clip_jobs WHERE status = 'paid') AS paid,
              (SELECT COUNT(*)::int FROM clip_jobs WHERE status = 'failed') AS failed,
              (SELECT COUNT(*)::int FROM clip_jobs WHERE status = 'rejected') AS rejected,
              (SELECT COALESCE(SUM(payout_amount),0) FROM clip_jobs WHERE status = 'paid') AS payout_total,
              (SELECT COUNT(*)::int FROM clip_campaigns c
               WHERE c.status = 'open'
                 AND NOT EXISTS (
                   SELECT 1 FROM clip_jobs j
                   WHERE j.campaign_id = c.id AND j.status = ANY($1::text[])
                 )) AS workable_campaigns
            """,
            list(ACTIVE_JOB_STATUSES),
        )
    return {
        "open_campaigns": row["open_campaigns"] or 0,
        "total_campaigns": row["total_campaigns"] or 0,
        "total_jobs": row["total_jobs"] or 0,
        "queued": row["queued"] or 0,
        "producing": row["producing"] or 0,
        "qa": row["qa"] or 0,
        "ready": row["ready"] or 0,
        "submitted": row["submitted"] or 0,
        "paid": row["paid"] or 0,
        "failed": row["failed"] or 0,
        "rejected": row["rejected"] or 0,
        "payout_total": float(row["payout_total"] or 0),
        "workable_campaigns": row["workable_campaigns"] or 0,
        "in_flight": (row["queued"] or 0) + (row["producing"] or 0) + (row["qa"] or 0),
    }
