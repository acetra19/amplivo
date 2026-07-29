"""Affiliate URL resolution for outbound and reply flows."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from packages.shared.config import settings
from packages.shared.db import get_connection
from packages.shared.settings_store import get_runtime


async def get_affiliate_url(lead_id: UUID | str | None = None) -> str | None:
    url = await get_runtime("affiliate_tracking_base")
    if url and "YOUR-AFFILIATE" not in url:
        return _with_lead_tracking(url, lead_id)

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
    return _with_lead_tracking(url, lead_id)


def _with_lead_tracking(url: str, lead_id: UUID | str | None) -> str:
    if not lead_id:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("utm_source", "amplivo")
    query.setdefault("utm_medium", "email")
    query["utm_content"] = str(lead_id)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
