"""Brevo (Sendinblue) transactional email client."""

from __future__ import annotations

import httpx

from packages.shared.config import settings
from packages.shared.settings_store import get_runtime

BREVO_API = "https://api.brevo.com/v3/smtp/email"


class BrevoError(Exception):
    pass


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    *,
    html: bool = False,
    to_name: str | None = None,
) -> dict:
    api_key = await get_runtime("brevo_api_key")
    if not api_key:
        raise BrevoError("BREVO_API_KEY not configured – set it in Dashboard → Settings")

    from_email = await get_runtime("outbound_from_email") or settings.outbound_from_email
    from_name = await get_runtime("outbound_from_name") or settings.outbound_from_name

    payload = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
    }
    if html:
        payload["htmlContent"] = body
    else:
        payload["textContent"] = body

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            BREVO_API,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code not in (200, 201):
            raise BrevoError(f"Brevo send failed ({resp.status_code}): {resp.text}")
        return resp.json()
