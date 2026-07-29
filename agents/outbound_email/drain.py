"""Quota drain – send follow-ups then first touches until daily limit."""

from __future__ import annotations

from packages.shared.brevo import BrevoError
from packages.shared.db import get_outreach_candidates
from packages.shared.rate_limit import remaining_quota
from packages.shared.settings_store import get_runtime


async def drain_outbound_quota(agent, *, max_new: int | None = None) -> dict:
    """
    1) Process due follow-ups
    2) Send first emails to top-scored ready leads until quota is empty
    """
    followups = await agent.process_followup_queue()
    remaining = await remaining_quota()
    if remaining <= 0:
        return {
            "followups": followups,
            "new_sends": [],
            "sent_new": 0,
            "remaining_quota": 0,
            "reason": "daily_limit_reached",
        }

    budget = remaining if max_new is None else min(remaining, max_new)
    threshold = int(await get_runtime("lead_score_threshold") or 70)
    candidates = await get_outreach_candidates(limit=max(budget * 2, 10))

    sent: list[dict] = []
    for lead in candidates:
        if len(sent) >= budget:
            break
        if await remaining_quota() <= 0:
            break

        lead_id = lead["id"]
        score = int(lead["score"] or 0)
        if score <= 0:
            try:
                scored = await agent.score_lead(lead_id)
                score = scored.score
            except Exception as exc:
                sent.append({"lead_id": str(lead_id), "skipped": True, "reason": f"score_failed:{exc}"})
                continue

        sequence = "outbound_a" if score >= threshold else "nurture_b"
        try:
            result = await agent.send_sequence_step(lead_id, sequence, 1)
        except BrevoError as exc:
            sent.append({"lead_id": str(lead_id), "email": lead["email"], "error": str(exc)})
            break

        sent.append(
            {
                "lead_id": str(lead_id),
                "email": lead["email"],
                "score": score,
                "sequence": sequence,
                **result,
            }
        )
        if result.get("skipped") and result.get("reason") == "daily_limit_reached":
            break

    return {
        "followups": followups,
        "new_sends": sent,
        "sent_new": sum(1 for s in sent if s.get("sent")),
        "remaining_quota": await remaining_quota(),
    }
