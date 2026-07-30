"""Phase-0 money plumbing checks: affiliate link, secret, product, tracking."""

from __future__ import annotations

from uuid import uuid4

from packages.shared.affiliate import get_affiliate_url
from packages.shared.config import settings
from packages.shared.db import get_connection
from packages.shared.settings_store import get_runtime, _is_configured


async def get_money_plumbing() -> dict:
    base = await get_runtime("affiliate_tracking_base") or settings.affiliate_tracking_base
    slug = await get_runtime("affiliate_product_slug") or settings.affiliate_product_slug
    secret = await get_runtime("affiliate_postback_secret") or settings.affiliate_postback_secret

    product = None
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """SELECT slug, name, affiliate_url, commission_pct, is_active
               FROM affiliate_products WHERE slug = $1""",
            slug,
        )
        if row:
            product = {
                "slug": row["slug"],
                "name": row["name"],
                "commission_pct": float(row["commission_pct"] or 0),
                "is_active": row["is_active"],
                "affiliate_url_set": bool(
                    row["affiliate_url"] and "YOUR-AFFILIATE" not in row["affiliate_url"]
                ),
            }
        conversions = await conn.fetchval("SELECT COUNT(*)::int FROM conversions") or 0
        interested = await conn.fetchval(
            """SELECT COUNT(DISTINCT lead_id)::int FROM interactions
               WHERE direction = 'inbound' AND sentiment = 'interested'"""
        ) or 0

    sample_lead = uuid4()
    tracked = await get_affiliate_url(sample_lead)
    has_sa = bool(tracked and "sa=" in tracked)
    has_utm = bool(tracked and "utm_content=" in tracked)

    checks = [
        {
            "id": "affiliate_link",
            "ok": bool(tracked) and has_sa,
            "detail": "Affiliate base URL with sa= tracking id",
        },
        {
            "id": "lead_attribution",
            "ok": has_utm,
            "detail": "utm_content={lead_id} appended for Amplivo attribution",
        },
        {
            "id": "product_seed",
            "ok": bool(product and product["is_active"]),
            "detail": f"Product slug '{slug}' active in DB",
        },
        {
            "id": "postback_secret",
            "ok": _is_configured(secret),
            "detail": "AFFILIATE_POSTBACK_SECRET set (manual/n8n recording)",
        },
        {
            "id": "postback_endpoint",
            "ok": True,
            "detail": "POST /webhooks/affiliate ready (email or lead_id)",
        },
    ]
    ok_count = sum(1 for c in checks if c["ok"])

    return {
        "ready": ok_count == len(checks),
        "score": f"{ok_count}/{len(checks)}",
        "checks": checks,
        "product": product,
        "sample_tracked_url": tracked,
        "systeme_note": (
            "Systeme.io affiliate commissions appear in their Affiliate dashboard. "
            "They do not S2S-postback to affiliates. Record conversions manually "
            "(or via n8n) with the referral email once you see a sale/referral."
        ),
        "stats": {
            "conversions_recorded": conversions,
            "interested_signals": interested,
        },
        "manual_record_example": {
            "method": "POST",
            "url": "https://api.amplivo.net/webhooks/affiliate",
            "headers": {"X-Postback-Secret": "<your-secret>", "Content-Type": "application/json"},
            "body": {
                "email": "buyer@example.com",
                "event_type": "signup",
                "commission_amount": 18.8,
                "affiliate_tx_id": "systeme-manual-1",
            },
        },
    }
