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

    allow_new_raw = (await get_runtime("outbound_allow_new_sends") or "true").strip().lower()
    allow_new = allow_new_raw not in {"0", "false", "no", "off"}
    if not allow_new:
        return {
            "followups": followups,
            "new_sends": [],
            "sent_new": 0,
            "remaining_quota": remaining,
            "reason": "new_sends_disabled",
        }

    budget = remaining if max_new is None else min(remaining, max_new)
    threshold = int(await get_runtime("lead_score_threshold") or 70)
    candidates = await get_outreach_candidates(limit=max(budget * 3, 15))

    sent: list[dict] = []
    sent_ok = 0
    for lead in candidates:
        if sent_ok >= budget:
            break
        if await remaining_quota() <= 0:
            break

        lead_id = lead["id"]
        email = (lead["email"] or "").lower()
        if email.endswith("@example.com") or "amplivo" in email or email.startswith("test-") or "llm-probe" in email:
            sent.append(
                {
                    "lead_id": str(lead_id),
                    "email": lead["email"],
                    "skipped": True,
                    "reason": "test_or_internal",
                }
            )
            continue
        score = int(lead["score"] or 0)
        if score <= 0:
            try:
                scored = await agent.score_lead(lead_id)
                score = scored.score
            except Exception as exc:
                sent.append(
                    {
                        "lead_id": str(lead_id),
                        "email": lead["email"],
                        "skipped": True,
                        "reason": f"score_failed:{exc}",
                    }
                )
                continue

        sequence = "outbound_a" if score >= threshold else "nurture_b"
        try:
            result = await agent.send_sequence_step(lead_id, sequence, 1)
        except BrevoError as exc:
            sent.append({"lead_id": str(lead_id), "email": lead["email"], "error": str(exc)})
            break
        except Exception as exc:
            # Keep draining; one bad personalize/LLM call must not 500 the whole job
            sent.append(
                {
                    "lead_id": str(lead_id),
                    "email": lead["email"],
                    "score": score,
                    "sequence": sequence,
                    "skipped": True,
                    "reason": f"send_failed:{type(exc).__name__}:{exc}",
                }
            )
            continue

        row = {
            "lead_id": str(lead_id),
            "email": lead["email"],
            "score": score,
            "sequence": sequence,
            **result,
        }
        sent.append(row)
        if result.get("skipped") and result.get("reason") == "daily_limit_reached":
            break
        if result.get("sent"):
            sent_ok += 1

    return {
        "followups": followups,
        "new_sends": sent,
        "sent_new": sent_ok,
        "remaining_quota": await remaining_quota(),
    }
