"""Reply inbox – inbound emails that may need an individual human/agent response."""

from __future__ import annotations

from datetime import datetime, timezone

from packages.shared.affiliate import get_affiliate_url
from packages.shared.db import get_connection

TEST_EMAIL_MARKERS = (
    "amplivo.net",
    "levelyourlife",
    "deine-domain.de",
    "example.com",
    "test@",
)


def _is_test_email(email: str) -> bool:
    lowered = (email or "").lower()
    return any(m in lowered for m in TEST_EMAIL_MARKERS)


async def get_reply_inbox(days: int = 14, limit: int = 40) -> dict:
    days = max(1, min(days, 60))
    limit = max(1, min(limit, 100))

    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
              i.id AS interaction_id,
              i.lead_id,
              i.created_at,
              i.sentiment,
              i.summary,
              i.subject,
              LEFT(i.body, 1200) AS body_preview,
              l.email,
              l.first_name,
              l.company,
              l.status::text AS status,
              l.do_not_contact,
              EXISTS (
                SELECT 1 FROM interactions o
                WHERE o.lead_id = i.lead_id
                  AND o.channel = 'email'
                  AND o.direction = 'outbound'
                  AND o.created_at > i.created_at
              ) AS has_outbound_after,
              EXISTS (
                SELECT 1 FROM interactions o
                WHERE o.lead_id = i.lead_id
                  AND o.channel = 'email'
                  AND o.direction = 'outbound'
                  AND o.created_at > i.created_at
                  AND COALESCE(o.metadata->>'kind', '') = 'auto_reply'
              ) AS has_auto_reply_after,
              EXISTS (
                SELECT 1 FROM interactions o
                WHERE o.lead_id = i.lead_id
                  AND o.channel = 'email'
                  AND o.direction = 'outbound'
                  AND o.created_at > i.created_at
                  AND COALESCE(o.metadata->>'kind', '') <> 'auto_reply'
              ) AS has_human_outbound_after
            FROM interactions i
            JOIN leads l ON l.id = i.lead_id
            WHERE i.channel = 'email'
              AND i.direction = 'inbound'
              AND i.created_at >= now() - ($1::text || ' days')::interval
            ORDER BY i.created_at DESC
            LIMIT $2
            """,
            str(days),
            limit,
        )

    now = datetime.now(timezone.utc)
    items: list[dict] = []
    needs_action: list[dict] = []

    for r in rows:
        email = r["email"]
        sentiment = (r["sentiment"] or "unknown").lower()
        is_test = _is_test_email(email)
        has_out = bool(r["has_outbound_after"])
        has_auto = bool(r["has_auto_reply_after"])
        has_human = bool(r["has_human_outbound_after"])
        created = r["created_at"]
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_hours = (now - created).total_seconds() / 3600

        status = (r["status"] or "").lower()
        closed = (
            bool(r.get("do_not_contact"))
            or sentiment in {"unsubscribe", "not_interested", "out_of_office"}
            or status in {"unsubscribed", "converted"}
        )
        reason = None
        if not is_test and not closed:
            if not has_out:
                reason = (
                    "interested_no_reply"
                    if sentiment == "interested"
                    else "unanswered_reply"
                )
            elif (
                sentiment == "interested"
                and has_auto
                and not has_human
                and age_hours >= 20
                and age_hours <= 24 * 7
            ):
                reason = "interested_nudge"
            elif sentiment == "objection" and not has_human:
                reason = "objection_review"

        item = {
            "interaction_id": str(r["interaction_id"]),
            "lead_id": str(r["lead_id"]),
            "at": r["created_at"].isoformat(),
            "email": email,
            "first_name": r["first_name"],
            "company": r["company"],
            "status": r["status"],
            "sentiment": sentiment,
            "summary": r["summary"],
            "subject": r["subject"],
            "body_preview": r["body_preview"],
            "has_outbound_after": has_out,
            "has_auto_reply_after": has_auto,
            "has_human_outbound_after": has_human,
            "age_hours": round(age_hours, 1),
            "is_test": is_test,
            "needs_action": bool(reason),
            "action_reason": reason,
        }
        items.append(item)
        if reason:
            needs_action.append(item)

    # Attach tracked affiliate URLs for actionable rows (GUI reply presets).
    for item in needs_action:
        try:
            item["affiliate_url"] = await get_affiliate_url(item["lead_id"])
        except Exception:
            item["affiliate_url"] = None

    return {
        "days": days,
        "total_inbound": len(items),
        "needs_action_count": len(needs_action),
        "needs_action": needs_action,
        "recent": items,
    }
