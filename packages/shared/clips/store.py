"""DB access for Amplivo Clips campaigns and jobs."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from packages.shared.db import get_connection


async def create_campaign(data: dict[str, Any]) -> UUID:
    external_id = data.get("external_id") or f"manual-{uuid4().hex[:12]}"
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO clip_campaigns (
              marketplace, external_id, title, source_url, brief,
              payout_model, payout_rate, currency, metadata
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)
            ON CONFLICT (marketplace, external_id) DO UPDATE SET
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


async def get_campaign(campaign_id: UUID):
    async with get_connection() as conn:
        return await conn.fetchrow("SELECT * FROM clip_campaigns WHERE id = $1", campaign_id)


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
            SELECT j.*, c.title AS campaign_title, c.source_url, c.marketplace, c.brief
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
            SELECT j.id, j.status, j.qa_score, j.clip_url, j.post_url, j.payout_amount,
                   j.created_at, c.title AS campaign_title, c.marketplace
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
              COUNT(*) FILTER (WHERE status = 'open')::int AS open_campaigns,
              (SELECT COUNT(*)::int FROM clip_jobs) AS total_jobs,
              (SELECT COUNT(*)::int FROM clip_jobs WHERE status = 'submitted') AS submitted,
              (SELECT COUNT(*)::int FROM clip_jobs WHERE status = 'paid') AS paid,
              (SELECT COALESCE(SUM(payout_amount),0) FROM clip_jobs WHERE status = 'paid') AS payout_total
            FROM clip_campaigns
            """
        )
    return {
        "open_campaigns": row["open_campaigns"],
        "total_jobs": row["total_jobs"],
        "submitted": row["submitted"],
        "paid": row["paid"],
        "payout_total": float(row["payout_total"] or 0),
    }
