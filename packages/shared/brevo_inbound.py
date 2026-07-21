"""Parse Brevo inbound webhook payloads into a normalized shape."""

from __future__ import annotations

from typing import Any


def _mailbox_email(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower() or None
    if isinstance(value, dict):
        for key in ("Address", "address", "Email", "email"):
            if value.get(key):
                return str(value[key]).strip().lower()
    return None


def _first_item(raw: dict[str, Any]) -> dict[str, Any] | None:
    items = raw.get("items")
    if isinstance(items, list) and items:
        first = items[0]
        return first if isinstance(first, dict) else None
    return None


def parse_brevo_inbound(raw: dict[str, Any]) -> dict[str, str | None] | None:
    """Return {from_email, subject, text} or None if sender cannot be resolved."""
    if not raw:
        return None

    # Legacy / manual API format
    if raw.get("from_email"):
        return {
            "from_email": str(raw["from_email"]).strip().lower(),
            "subject": raw.get("subject"),
            "text": (raw.get("text") or raw.get("html") or "").strip(),
        }

    item = _first_item(raw) or raw

    from_email = (
        _mailbox_email(item.get("From"))
        or _mailbox_email(item.get("from"))
        or _mailbox_email(item.get("Sender"))
        or (str(item["sender"]).strip().lower() if item.get("sender") else None)
    )
    if not from_email:
        return None

    subject = item.get("Subject") or item.get("subject")
    text = (
        item.get("ExtractedMarkdownMessage")
        or item.get("RawTextBody")
        or item.get("text")
        or item.get("TextBody")
        or item.get("html")
        or item.get("RawHtmlBody")
        or ""
    )
    return {
        "from_email": from_email,
        "subject": subject,
        "text": str(text).strip(),
    }
