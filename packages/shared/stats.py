"""Pipeline and dashboard statistics."""

from __future__ import annotations

from packages.shared.db import get_connection
from packages.shared.queue import voice_queue_length


async def get_pipeline_stats() -> dict:
    async with get_connection() as conn:
        by_status = await conn.fetch(
            """SELECT status::text, COUNT(*) AS count FROM leads
               GROUP BY status ORDER BY count DESC"""
        )
        totals = await conn.fetchrow(
            """SELECT
                 COUNT(*) AS total_leads,
                 COUNT(*) FILTER (WHERE icp_match) AS icp_leads,
                 COUNT(*) FILTER (WHERE status = 'converted') AS conversions,
                 COALESCE(SUM(c.commission_amount), 0) AS total_commission
               FROM leads l
               LEFT JOIN conversions c ON c.lead_id = l.id"""
        )
        today = await conn.fetchrow(
            """SELECT
                 COUNT(*) FILTER (WHERE channel = 'email' AND direction = 'outbound') AS emails_sent,
                 COUNT(*) FILTER (WHERE channel = 'email' AND direction = 'inbound') AS emails_replied
               FROM interactions WHERE created_at::date = CURRENT_DATE"""
        )

    return {
        "total_leads": totals["total_leads"],
        "icp_leads": totals["icp_leads"],
        "conversions": totals["conversions"],
        "total_commission": float(totals["total_commission"]),
        "emails_sent_today": today["emails_sent"],
        "emails_replied_today": today["emails_replied"],
        "voice_queue_length": await voice_queue_length(),
        "leads_by_status": {r["status"]: r["count"] for r in by_status},
    }
