"""Actionable ops insights for the improvement dashboard."""

from __future__ import annotations

from packages.shared.db import get_connection
from packages.shared.queue import voice_queue_length
from packages.shared.rate_limit import get_today_sent_count, remaining_quota, _daily_limit


def _pct(num: float, den: float) -> float:
    if not den:
        return 0.0
    return round(num / den * 100, 2)


def _build_recommendations(data: dict) -> list[dict]:
    tips: list[dict] = []
    email = data["email"]
    quality = data["lead_quality"]
    seq = data["sequences"]
    funnel = data["funnel"]

    if email["sent_today"] < email["daily_limit"] * 0.5 and email["remaining"] > 0:
        tips.append({
            "severity": "high",
            "area": "throughput",
            "title": "Daily quota underused",
            "detail": (
                f"Only {email['sent_today']}/{email['daily_limit']} emails sent today "
                f"({email['remaining']} left). Check hourly discovery + drain-quota workflows."
            ),
            "metric": "quota_utilization_pct",
            "value": email["quota_utilization_pct"],
        })

    if email["sent_7d"] >= 20 and email["reply_rate_7d"] < 2:
        tips.append({
            "severity": "high",
            "area": "conversion",
            "title": "Reply rate too low",
            "detail": (
                f"7-day reply rate is {email['reply_rate_7d']}% "
                f"({email['replies_7d']} replies / {email['sent_7d']} sends). "
                "Improve subject lines, lead quality, and deliverability."
            ),
            "metric": "reply_rate_7d",
            "value": email["reply_rate_7d"],
        })

    if quality["info_email_pct"] >= 40:
        tips.append({
            "severity": "medium",
            "area": "lead_quality",
            "title": "Too many generic inboxes",
            "detail": (
                f"{quality['info_email_pct']}% of emails are info@/contact@ style. "
                "Prioritize personal founder/coach addresses."
            ),
            "metric": "info_email_pct",
            "value": quality["info_email_pct"],
        })

    if quality["icp_pct"] < 50 and funnel["total_leads"] >= 20:
        tips.append({
            "severity": "medium",
            "area": "lead_quality",
            "title": "ICP match rate weak",
            "detail": (
                f"Only {quality['icp_pct']}% ICP matches. Tighten discovery seeds "
                "and scoring for coaches/creators 1–20 employees."
            ),
            "metric": "icp_pct",
            "value": quality["icp_pct"],
        })

    if seq["overdue"] > 0:
        tips.append({
            "severity": "medium",
            "area": "sequences",
            "title": "Follow-ups overdue",
            "detail": (
                f"{seq['overdue']} sequences have next_send_at in the past. "
                "Ensure drain-quota runs at 09:00 and 14:00."
            ),
            "metric": "sequences_overdue",
            "value": seq["overdue"],
        })

    if email["sent_7d"] >= 10 and email["replies_7d"] == 0:
        tips.append({
            "severity": "high",
            "area": "deliverability",
            "title": "Zero replies after volume",
            "detail": (
                "Sends without replies often signal spam folder or weak offer. "
                "Verify SPF/DKIM/DMARC and test inbox placement."
            ),
            "metric": "replies_7d",
            "value": 0,
        })

    if funnel["interested"] > 0 and funnel["converted"] == 0:
        tips.append({
            "severity": "medium",
            "area": "tracking",
            "title": "Interest without conversions",
            "detail": (
                f"{funnel['interested']} interested signals but 0 conversions tracked. "
                "Confirm affiliate postbacks and UTM lead_id tracking."
            ),
            "metric": "conversions",
            "value": 0,
        })

    if not tips:
        tips.append({
            "severity": "low",
            "area": "ops",
            "title": "Pipeline looks healthy",
            "detail": "No critical bottlenecks detected. Keep filling quota and monitor reply quality.",
            "metric": "health",
            "value": 1,
        })

    order = {"high": 0, "medium": 1, "low": 2}
    tips.sort(key=lambda t: order.get(t["severity"], 9))
    return tips


async def get_ops_insights() -> dict:
    async with get_connection() as conn:
        status_rows = await conn.fetch(
            """SELECT status::text AS status, COUNT(*)::int AS count
               FROM leads GROUP BY status ORDER BY count DESC"""
        )
        totals = await conn.fetchrow(
            """SELECT
                 COUNT(*)::int AS total_leads,
                 COUNT(*) FILTER (WHERE icp_match)::int AS icp_leads,
                 COUNT(*) FILTER (WHERE status = 'converted')::int AS converted,
                 COUNT(*) FILTER (
                   WHERE email ~* '^(info|contact|hello|office|mail|support)@'
                 )::int AS info_emails,
                 COALESCE(AVG(score), 0) AS avg_score
               FROM leads"""
        )
        interested = await conn.fetchval(
            """SELECT COUNT(DISTINCT lead_id)::int FROM interactions
               WHERE direction = 'inbound' AND sentiment = 'interested'"""
        ) or 0
        email_totals = await conn.fetchrow(
            """SELECT
                 COUNT(*) FILTER (
                   WHERE channel = 'email' AND direction = 'outbound'
                     AND created_at::date = CURRENT_DATE
                 )::int AS sent_today,
                 COUNT(*) FILTER (
                   WHERE channel = 'email' AND direction = 'inbound'
                     AND created_at::date = CURRENT_DATE
                 )::int AS replies_today,
                 COUNT(*) FILTER (
                   WHERE channel = 'email' AND direction = 'outbound'
                     AND created_at >= CURRENT_DATE - INTERVAL '7 days'
                 )::int AS sent_7d,
                 COUNT(*) FILTER (
                   WHERE channel = 'email' AND direction = 'inbound'
                     AND created_at >= CURRENT_DATE - INTERVAL '7 days'
                 )::int AS replies_7d,
                 COUNT(*) FILTER (
                   WHERE channel = 'email' AND direction = 'outbound'
                     AND created_at >= CURRENT_DATE - INTERVAL '30 days'
                 )::int AS sent_30d,
                 COUNT(*) FILTER (
                   WHERE channel = 'email' AND direction = 'inbound'
                     AND created_at >= CURRENT_DATE - INTERVAL '30 days'
                 )::int AS replies_30d
               FROM interactions"""
        )
        sentiment_rows = await conn.fetch(
            """SELECT COALESCE(sentiment, 'unknown') AS sentiment, COUNT(*)::int AS count
               FROM interactions
               WHERE channel = 'email' AND direction = 'inbound'
                 AND created_at >= CURRENT_DATE - INTERVAL '30 days'
               GROUP BY 1 ORDER BY count DESC"""
        )
        industry_rows = await conn.fetch(
            """SELECT COALESCE(NULLIF(TRIM(industry), ''), 'unknown') AS industry,
                      COUNT(*)::int AS count
               FROM leads GROUP BY 1 ORDER BY count DESC LIMIT 8"""
        )
        source_rows = await conn.fetch(
            """SELECT COALESCE(NULLIF(TRIM(source), ''), 'unknown') AS source,
                      COUNT(*)::int AS count
               FROM leads GROUP BY 1 ORDER BY count DESC LIMIT 8"""
        )
        seq = await conn.fetchrow(
            """SELECT
                 COUNT(*) FILTER (WHERE NOT completed AND NOT paused)::int AS active,
                 COUNT(*) FILTER (WHERE paused)::int AS paused,
                 COUNT(*) FILTER (WHERE completed)::int AS completed,
                 COUNT(*) FILTER (
                   WHERE NOT completed AND NOT paused
                     AND next_send_at IS NOT NULL AND next_send_at < now()
                 )::int AS overdue
               FROM lead_sequence_state"""
        ) or {"active": 0, "paused": 0, "completed": 0, "overdue": 0}

        trend_rows = await conn.fetch(
            """SELECT d::date AS day,
                      COUNT(i.id) FILTER (
                        WHERE i.channel = 'email' AND i.direction = 'outbound'
                      )::int AS sent,
                      COUNT(i.id) FILTER (
                        WHERE i.channel = 'email' AND i.direction = 'inbound'
                      )::int AS replies
               FROM generate_series(CURRENT_DATE - INTERVAL '13 days', CURRENT_DATE, '1 day') d
               LEFT JOIN interactions i ON i.created_at::date = d::date
               GROUP BY 1 ORDER BY 1"""
        )
        recent_replies = await conn.fetch(
            """SELECT i.created_at, i.sentiment, i.summary, i.subject,
                      l.email, l.company, l.status::text AS status
               FROM interactions i
               JOIN leads l ON l.id = i.lead_id
               WHERE i.channel = 'email' AND i.direction = 'inbound'
               ORDER BY i.created_at DESC LIMIT 12"""
        )
        ready_pool = await conn.fetchval(
            """SELECT COUNT(*)::int FROM leads l
               WHERE l.do_not_contact = false
                 AND l.status IN ('new', 'enriched')
                 AND l.icp_match = true
                 AND NOT EXISTS (
                   SELECT 1 FROM lead_sequence_state s WHERE s.lead_id = l.id
                 )
                 AND NOT EXISTS (
                   SELECT 1 FROM interactions i
                   WHERE i.lead_id = l.id AND i.channel = 'email'
                     AND i.direction = 'outbound'
                 )"""
        ) or 0
        commission = await conn.fetchval(
            "SELECT COALESCE(SUM(commission_amount), 0) FROM conversions"
        ) or 0

    daily_limit = await _daily_limit()
    sent_today = await get_today_sent_count()
    remaining = await remaining_quota()

    by_status = {r["status"]: r["count"] for r in status_rows}
    funnel = {
        "total_leads": totals["total_leads"],
        "new": by_status.get("new", 0),
        "enriched": by_status.get("enriched", 0),
        "contacted": by_status.get("contacted", 0),
        "replied": by_status.get("replied", 0),
        "qualified": by_status.get("qualified", 0),
        "interested": interested,
        "converted": totals["converted"],
        "lost": by_status.get("lost", 0),
        "unsubscribed": by_status.get("unsubscribed", 0),
        "leads_by_status": by_status,
    }
    email = {
        "sent_today": sent_today,
        "replies_today": email_totals["replies_today"],
        "daily_limit": daily_limit,
        "remaining": remaining,
        "quota_utilization_pct": _pct(sent_today, daily_limit),
        "sent_7d": email_totals["sent_7d"],
        "replies_7d": email_totals["replies_7d"],
        "reply_rate_7d": _pct(email_totals["replies_7d"], email_totals["sent_7d"]),
        "sent_30d": email_totals["sent_30d"],
        "replies_30d": email_totals["replies_30d"],
        "reply_rate_30d": _pct(email_totals["replies_30d"], email_totals["sent_30d"]),
        "interested_rate_30d": _pct(interested, max(email_totals["sent_30d"], 1)),
    }
    lead_quality = {
        "icp_leads": totals["icp_leads"],
        "icp_pct": _pct(totals["icp_leads"], totals["total_leads"]),
        "info_emails": totals["info_emails"],
        "info_email_pct": _pct(totals["info_emails"], totals["total_leads"]),
        "avg_score": round(float(totals["avg_score"]), 1),
        "ready_pool": ready_pool,
        "by_industry": [{"name": r["industry"], "count": r["count"]} for r in industry_rows],
        "by_source": [{"name": r["source"], "count": r["count"]} for r in source_rows],
    }
    sequences = {
        "active": seq["active"],
        "paused": seq["paused"],
        "completed": seq["completed"],
        "overdue": seq["overdue"],
    }

    payload = {
        "funnel": funnel,
        "email": email,
        "lead_quality": lead_quality,
        "sequences": sequences,
        "reply_sentiment_30d": [
            {"sentiment": r["sentiment"], "count": r["count"]} for r in sentiment_rows
        ],
        "trend_14d": [
            {
                "day": r["day"].isoformat(),
                "sent": r["sent"],
                "replies": r["replies"],
            }
            for r in trend_rows
        ],
        "recent_replies": [
            {
                "at": r["created_at"].isoformat(),
                "email": r["email"],
                "company": r["company"],
                "status": r["status"],
                "sentiment": r["sentiment"],
                "summary": r["summary"],
                "subject": r["subject"],
            }
            for r in recent_replies
        ],
        "voice_queue_length": await voice_queue_length(),
        "total_commission": float(commission),
    }
    payload["recommendations"] = _build_recommendations(payload)
    return payload
