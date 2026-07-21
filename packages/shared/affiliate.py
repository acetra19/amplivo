"""Affiliate URL resolution for outbound and reply flows."""

from __future__ import annotations

from packages.shared.config import settings
from packages.shared.db import get_connection
from packages.shared.settings_store import get_runtime


async def get_affiliate_url() -> str | None:
    url = await get_runtime("affiliate_tracking_base")
    if url and "YOUR-AFFILIATE" not in url:
        return url

    slug = await get_runtime("affiliate_product_slug") or settings.affiliate_product_slug
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """SELECT affiliate_url FROM affiliate_products
               WHERE slug = $1 AND is_active = true""",
            slug,
        )
    if not row:
        return None
    url = row["affiliate_url"]
    if "YOUR-AFFILIATE" in url:
        return None
    return url
