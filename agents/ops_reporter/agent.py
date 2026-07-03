"""Ops reporter agent – daily metrics, ROI, campaign health."""

from __future__ import annotations

import time
from datetime import date, timedelta

from packages.shared.db import get_connection, log_agent_run
from packages.shared.llm import generate_text


class OpsReporterAgent:
    name = "ops_reporter"

    async def collect_daily_metrics(self, metric_date: date | None = None) -> dict:
        start = time.monotonic()
        metric_date = metric_date or date.today()

        async with get_connection() as conn:
            emails_sent = await conn.fetchval(
                """SELECT COUNT(*) FROM interactions
                   WHERE channel = 'email' AND direction = 'outbound'
                   AND created_at::date = $1""",
                metric_date,
            )
            emails_replied = await conn.fetchval(
                """SELECT COUNT(*) FROM interactions
                   WHERE channel = 'email' AND direction = 'inbound'
                   AND created_at::date = $1""",
                metric_date,
            )
            leads_qualified = await conn.fetchval(
                """SELECT COUNT(*) FROM leads
                   WHERE status = 'qualified' AND updated_at::date = $1""",
                metric_date,
            )
            trials_started = await conn.fetchval(
                """SELECT COUNT(*) FROM conversions
                   WHERE event_type = 'trial_start' AND occurred_at::date = $1""",
                metric_date,
            )
            conversions = await conn.fetchval(
                """SELECT COUNT(*) FROM conversions
                   WHERE event_type = 'signup' AND occurred_at::date = $1""",
                metric_date,
            )
            commission_total = await conn.fetchval(
                """SELECT COALESCE(SUM(commission_amount), 0) FROM conversions
                   WHERE occurred_at::date = $1""",
                metric_date,
            ) or 0

            await conn.execute(
                """INSERT INTO daily_metrics (
                    metric_date, emails_sent, emails_replied, leads_qualified,
                    trials_started, conversions, commission_total
                ) VALUES ($1,$2,$3,$4,$5,$6,$7)
                ON CONFLICT (metric_date) DO UPDATE SET
                    emails_sent = EXCLUDED.emails_sent,
                    emails_replied = EXCLUDED.emails_replied,
                    leads_qualified = EXCLUDED.leads_qualified,
                    trials_started = EXCLUDED.trials_started,
                    conversions = EXCLUDED.conversions,
                    commission_total = EXCLUDED.commission_total""",
                metric_date, emails_sent, emails_replied, leads_qualified,
                trials_started, conversions, commission_total,
            )

        metrics = {
            "date": str(metric_date),
            "emails_sent": emails_sent,
            "emails_replied": emails_replied,
            "reply_rate": round(emails_replied / max(emails_sent, 1) * 100, 2),
            "leads_qualified": leads_qualified,
            "trials_started": trials_started,
            "conversions": conversions,
            "commission_total": float(commission_total),
        }

        await log_agent_run(
            self.name,
            input_summary=f"Daily metrics {metric_date}",
            output_summary=f"Sent={emails_sent}, Conv={conversions}",
            duration_ms=int((time.monotonic() - start) * 1000),
            metadata=metrics,
        )
        return metrics

    async def generate_report(self, days: int = 7) -> str:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """SELECT * FROM daily_metrics
                   WHERE metric_date >= $1 ORDER BY metric_date DESC""",
                date.today() - timedelta(days=days),
            )

        data = [dict(r) for r in rows]
        prompt = f"""Generate a concise English ops report for the sales agency leadership.
Include: trends, anomalies, recommendations. Use bullet points.

Last {days} days metrics:
{data}"""

        return await generate_text(prompt, "You are a revenue operations analyst.")
