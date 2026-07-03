"""Daily outbound email rate limiting – protects domain during lean bootstrap."""

from __future__ import annotations

from datetime import date

from packages.shared.config import settings
from packages.shared.db import get_connection
from packages.shared.settings_store import get_runtime


async def _daily_limit() -> int:
    raw = await get_runtime("daily_email_limit")
    return int(raw) if raw else settings.daily_email_limit


async def get_today_sent_count() -> int:
    async with get_connection() as conn:
        return await conn.fetchval(
            """SELECT COUNT(*) FROM interactions
               WHERE channel = 'email' AND direction = 'outbound'
               AND created_at::date = $1""",
            date.today(),
        ) or 0


async def remaining_quota() -> int:
    sent = await get_today_sent_count()
    return max(0, await _daily_limit() - sent)


async def can_send() -> bool:
    return await remaining_quota() > 0
