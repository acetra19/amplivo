"""Ops action APIs for the Leads dashboard (ready pool, conversions, affiliate)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from packages.shared.affiliate import get_affiliate_url
from packages.shared.config import settings
from packages.shared.db import get_connection, get_lead_by_email, get_lead_by_id, get_outreach_candidates
from packages.shared.gamification import award_xp
from packages.shared.rate_limit import get_today_sent_count, remaining_quota
from packages.shared.settings_store import get_runtime

router = APIRouter(prefix="/ops", tags=["ops-leads"])

GENERIC_LOCAL = {
    "info", "contact", "kontakt", "hello", "hallo", "office", "mail",
    "team", "service", "anfrage", "beratung", "support",
}


def _is_generic_inbox(email: str) -> bool:
    local = (email or "").split("@", 1)[0].lower()
    return local in GENERIC_LOCAL


def _lead_row(r) -> dict:
    email = r["email"]
    created = r["created_at"]
    return {
        "id": str(r["id"]),
        "email": email,
        "first_name": r["first_name"],
        "company": r["company"],
        "job_title": r["job_title"],
        "score": r["score"],
        "status": str(r["status"]),
        "industry": r["industry"],
        "source": r["source"],
        "generic_inbox": _is_generic_inbox(email),
        "created_at": created.isoformat() if created else None,
    }


class RecordConversionRequest(BaseModel):
    email: EmailStr | None = None
    lead_id: UUID | None = None
    event_type: str = "signup"
    commission_amount: float | None = None
    affiliate_tx_id: str | None = None


@router.get("/leads/ready")
async def leads_ready(limit: int = 20):
    rows = await get_outreach_candidates(limit=max(1, min(limit, 50)))
    return {
        "leads": [_lead_row(r) for r in rows],
        "quota": {
            "sent_today": await get_today_sent_count(),
            "remaining": await remaining_quota(),
            "daily_limit": int(await get_runtime("daily_email_limit") or settings.daily_email_limit or 30),
        },
    }


@router.get("/leads/warm")
async def leads_warm(limit: int = 40):
    """Hot pipeline for revenue sprint: interested / qualified / replied, not DNC."""
    lim = max(1, min(limit, 100))
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            WITH inbound AS (
              SELECT DISTINCT ON (i.lead_id)
                     i.lead_id, i.sentiment, i.summary, i.body, i.created_at AS replied_at
              FROM interactions i
              WHERE i.direction = 'inbound' AND i.channel = 'email'
              ORDER BY i.lead_id, i.created_at DESC
            )
            SELECT l.*,
                   ib.sentiment AS last_sentiment,
                   ib.summary AS last_summary,
                   left(coalesce(ib.body, ''), 280) AS last_body,
                   ib.replied_at
            FROM leads l
            LEFT JOIN inbound ib ON ib.lead_id = l.id
            WHERE l.do_not_contact = false
              AND (
                l.status::text IN ('qualified', 'replied', 'trial_started')
                OR ib.sentiment IN ('interested', 'objection', 'other', 'out_of_office')
              )
              AND coalesce(ib.sentiment, '') <> 'unsubscribe'
            ORDER BY
              CASE
                WHEN l.status::text = 'qualified' OR ib.sentiment = 'interested' THEN 0
                WHEN l.status::text = 'replied' THEN 1
                ELSE 2
              END,
              coalesce(ib.replied_at, l.updated_at) DESC NULLS LAST
            LIMIT $1
            """,
            lim,
        )
    leads = []
    for r in rows:
        row = _lead_row(r)
        row["last_sentiment"] = r["last_sentiment"]
        row["last_summary"] = r["last_summary"]
        row["last_body"] = r["last_body"]
        row["replied_at"] = r["replied_at"].isoformat() if r["replied_at"] else None
        leads.append(row)
    return {"leads": leads, "count": len(leads)}


@router.get("/leads/{lead_id}/affiliate-url")
async def lead_affiliate_url(lead_id: UUID):
    lead = await get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    url = await get_affiliate_url(lead_id)
    return {
        "lead_id": str(lead_id),
        "email": lead["email"],
        "affiliate_url": url,
    }


@router.post("/record-conversion")
async def record_conversion(req: RecordConversionRequest):
    """GUI-safe conversion recorder — uses server-side postback secret."""
    if not req.email and not req.lead_id:
        raise HTTPException(status_code=400, detail="email or lead_id required")

    lead = None
    if req.lead_id:
        lead = await get_lead_by_id(req.lead_id)
    elif req.email:
        lead = await get_lead_by_email(req.email)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    expected = await get_runtime("affiliate_postback_secret") or settings.affiliate_postback_secret
    if not expected:
        raise HTTPException(status_code=500, detail="affiliate_postback_secret not configured")

    status_map = {"trial_start": "trial_started", "signup": "converted"}
    new_status = status_map.get(req.event_type)

    async with get_connection() as conn:
        product_slug = await get_runtime("affiliate_product_slug") or settings.affiliate_product_slug
        product = await conn.fetchrow(
            "SELECT id FROM affiliate_products WHERE slug = $1", product_slug,
        )
        if not product:
            raise HTTPException(status_code=500, detail=f"Product not found: {product_slug}")
        await conn.execute(
            """INSERT INTO conversions (lead_id, product_id, affiliate_tx_id, event_type, commission_amount)
               VALUES ($1, $2, $3, $4, $5)""",
            lead["id"],
            product["id"],
            req.affiliate_tx_id,
            req.event_type,
            req.commission_amount,
        )
        if new_status:
            await conn.execute(
                "UPDATE leads SET status = $2::lead_status WHERE id = $1",
                lead["id"],
                new_status,
            )

    xp_event = "trial_started" if req.event_type == "trial_start" else "conversion"
    gamification = {}
    if req.event_type in ("trial_start", "signup"):
        gamification = await award_xp(xp_event, f"{req.event_type}: {lead['email']}")

    return {"ok": True, "lead_id": str(lead["id"]), "gamification": gamification}
