"""Outbound email agent – scores leads, personalizes sequences, sends via Brevo."""

from __future__ import annotations

import time
from uuid import UUID

from packages.shared.affiliate import get_affiliate_url
from packages.shared.brevo import BrevoError, send_email
from packages.shared.config import settings
from packages.shared.db import (
    get_connection,
    get_due_followups,
    get_lead_by_id,
    get_sequence_state,
    get_sequence_step,
    log_agent_run,
    log_interaction,
    mark_sequence_completed,
    update_lead_score,
    upsert_sequence_state,
)
from packages.shared.gamification import award_xp
from packages.shared.llm import classify_text, extract_json, generate_text
from packages.shared.settings_store import get_runtime
from packages.shared.models import ClassifiedReply, LeadScoreResult, ReplyClassification
from packages.shared.queue import enqueue_voice_call
from packages.shared.rate_limit import can_send, remaining_quota


SCORE_SYSTEM = """You are a lead scoring agent for an affiliate sales agency selling Systeme.io.
ICP: solopreneurs, coaches, course creators, freelancers, small online businesses.
Score leads 0-100 based on ICP fit. Return ONLY valid JSON:
{"score": int, "icp_match": bool, "reasoning": str, "recommended_sequence": "outbound_a"|"nurture_b"}"""

REPLY_SYSTEM = """You classify cold email replies for a B2B sales agent.
Return ONLY valid JSON:
{
  "classification": "interested"|"objection"|"not_now"|"unsubscribe"|"out_of_office"|"other",
  "confidence": float,
  "summary": str,
  "suggested_response": str|null,
  "should_escalate_voice": bool
}"""


class OutboundEmailAgent:
    name = "outbound_email"

    async def score_lead(self, lead_id: UUID) -> LeadScoreResult:
        start = time.monotonic()
        lead = await get_lead_by_id(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        product = await get_runtime("affiliate_product_slug") or "systeme-io"
        icp = await get_runtime("icp_industry") or "online_business"
        min_emp = await get_runtime("icp_min_employees") or "1"
        max_emp = await get_runtime("icp_max_employees") or "20"

        prompt = f"""Score this lead for product: {product}
ICP: {icp}, {min_emp}-{max_emp} employees

Lead data:
- Email: {lead['email']}
- Name: {lead['first_name']} {lead['last_name']}
- Company: {lead['company']}
- Title: {lead['job_title']}
- Industry: {lead['industry']}
- Employees: {lead['employee_count']}
- Country: {lead['country']}
- Website: {lead['website']}"""

        raw = await classify_text(prompt, SCORE_SYSTEM)
        data = extract_json(raw)
        result = LeadScoreResult(**data)

        status = "enriched" if result.icp_match else "new"
        await update_lead_score(lead_id, result.score, result.icp_match, status)

        await log_agent_run(
            self.name,
            lead_id=lead_id,
            input_summary=f"Score lead {lead['email']}",
            output_summary=f"Score={result.score}, ICP={result.icp_match}",
            duration_ms=int((time.monotonic() - start) * 1000),
            metadata={"recommended_sequence": result.recommended_sequence},
        )
        return result

    async def send_sequence_step(self, lead_id: UUID, sequence_slug: str, step_order: int | None = None) -> dict:
        """Personalize and send one sequence step via Brevo."""
        start = time.monotonic()
        lead = await get_lead_by_id(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        if lead["do_not_contact"]:
            return {"skipped": True, "reason": "do_not_contact"}

        if not await can_send():
            return {"skipped": True, "reason": "daily_limit_reached", "remaining": 0}

        state = await get_sequence_state(lead_id, sequence_slug)
        if state and state["completed"]:
            return {"skipped": True, "reason": "sequence_completed"}

        if step_order is None:
            step_order = (state["current_step"] + 1) if state else 1

        step = await get_sequence_step(sequence_slug, step_order)
        if not step:
            await mark_sequence_completed(lead_id, sequence_slug)
            return {"skipped": True, "reason": "sequence_completed"}

        personalized = await self.personalize_email(lead_id, step["subject_tpl"], step["body_tpl"])

        try:
            await send_email(
                lead["email"],
                personalized["subject"],
                personalized["body"],
                to_name=lead["first_name"],
            )
        except BrevoError as exc:
            await log_agent_run(
                self.name, lead_id=lead_id, status="failed",
                error_message=str(exc), input_summary=f"Send step {step_order}",
            )
            raise

        await log_interaction(
            lead_id, channel="email", direction="outbound",
            subject=personalized["subject"], body=personalized["body"],
            agent_name=self.name,
            metadata={"sequence": sequence_slug, "step": step_order},
        )

        next_step = await get_sequence_step(sequence_slug, step_order + 1)
        if next_step:
            await upsert_sequence_state(lead_id, sequence_slug, step_order, next_step["delay_days"])
        else:
            await upsert_sequence_state(lead_id, sequence_slug, step_order, 0)
            await mark_sequence_completed(lead_id, sequence_slug)

        async with get_connection() as conn:
            await conn.execute(
                "UPDATE leads SET status = 'contacted'::lead_status, updated_at = now() WHERE id = $1",
                lead_id,
            )

        await log_agent_run(
            self.name, lead_id=lead_id,
            input_summary=f"Send {sequence_slug} step {step_order}",
            output_summary=personalized["subject"],
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        gamification = await award_xp("email_sent", f"Email to {lead['email']}")
        return {
            "sent": True,
            "subject": personalized["subject"],
            "step": step_order,
            "sequence": sequence_slug,
            "remaining_quota": await remaining_quota(),
            "gamification": gamification,
        }

    async def process_followup_queue(self) -> dict:
        """Send all due follow-up emails within daily quota."""
        quota = await remaining_quota()
        if quota == 0:
            return {"processed": 0, "reason": "daily_limit_reached"}

        due = await get_due_followups(quota)
        results = []
        for item in due:
            if item["current_step"] == 0:
                continue
            try:
                result = await self.send_sequence_step(
                    item["lead_id"], item["sequence_slug"], item["current_step"] + 1,
                )
                results.append(result)
            except BrevoError:
                break
        return {"processed": len(results), "results": results, "remaining_quota": await remaining_quota()}

    async def send_reply_email(self, lead_id: UUID, subject: str, body: str) -> dict:
        """Send a one-off reply (e.g. objection handling) via Brevo."""
        lead = await get_lead_by_id(lead_id)
        if not lead or lead["do_not_contact"]:
            return {"skipped": True, "reason": "do_not_contact"}
        if not await can_send():
            return {"skipped": True, "reason": "daily_limit_reached"}

        await send_email(lead["email"], subject, body, to_name=lead["first_name"])
        await log_interaction(
            lead_id, channel="email", direction="outbound",
            subject=subject, body=body, agent_name=self.name,
        )
        gamification = await award_xp("email_sent", f"Reply to {lead['email']}")
        return {"sent": True, "remaining_quota": await remaining_quota(), "gamification": gamification}

    async def personalize_email(
        self,
        lead_id: UUID,
        subject_tpl: str,
        body_tpl: str,
    ) -> dict[str, str]:
        lead = await get_lead_by_id(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        prompt = f"""Personalize this cold email template for the lead. Keep it concise, professional, in English.
Product context: all-in-one platform for online businesses (funnels, email, courses). Do not include affiliate links in cold emails.
Do not invent facts. Return JSON: {{"subject": str, "body": str}}

Lead: {dict(lead)}
Template subject: {subject_tpl}
Template body: {body_tpl}
Sender name: {settings.outbound_from_name}"""

        raw = await generate_text(prompt, "You write high-converting B2B cold emails.")
        return extract_json(raw)

    async def classify_reply(self, lead_id: UUID, reply_body: str) -> ClassifiedReply:
        start = time.monotonic()
        lead = await get_lead_by_id(lead_id)

        prompt = f"""Classify this email reply.

Original lead: {lead['email']}, {lead['company']}
Reply:
{reply_body}"""

        raw = await classify_text(prompt, REPLY_SYSTEM)
        data = extract_json(raw)
        result = ClassifiedReply(**data)

        await log_interaction(
            lead_id,
            channel="email",
            direction="inbound",
            body=reply_body,
            summary=result.summary,
            sentiment=result.classification.value,
            agent_name=self.name,
        )

        if result.classification == ReplyClassification.UNSUBSCRIBE:
            from packages.shared.db import get_connection
            async with get_connection() as conn:
                await conn.execute(
                    "UPDATE leads SET do_not_contact = true, status = 'unsubscribed' WHERE id = $1",
                    lead_id,
                )
        else:
            async with get_connection() as conn:
                await conn.execute(
                    "UPDATE leads SET status = 'replied'::lead_status, updated_at = now() WHERE id = $1",
                    lead_id,
                )

        await log_agent_run(
            self.name,
            lead_id=lead_id,
            input_summary="Classify email reply",
            output_summary=f"{result.classification.value} ({result.confidence:.2f})",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        await award_xp("email_reply", f"Reply from {lead['email']}")
        if result.classification == ReplyClassification.INTERESTED:
            await award_xp("reply_interested", f"Interested: {lead['email']}")
        return result

    async def handle_reply(
        self,
        lead_id: UUID,
        reply_body: str,
        subject: str | None = None,
    ) -> dict:
        """Classify inbound reply and auto-send trial link or objection response."""
        result = await self.classify_reply(lead_id, reply_body)
        payload = result.model_dump()
        payload["auto_reply"] = None

        if result.classification == ReplyClassification.INTERESTED:
            affiliate_url = await get_affiliate_url()
            if affiliate_url:
                subj, body = self._interested_reply(await get_lead_by_id(lead_id), affiliate_url)
                payload["auto_reply"] = await self.send_reply_email(lead_id, subj, body)
            async with get_connection() as conn:
                await conn.execute(
                    "UPDATE leads SET status = 'qualified'::lead_status, updated_at = now() WHERE id = $1",
                    lead_id,
                )
            payload["voice_queue"] = await enqueue_voice_call(lead_id, reason="interested")

        elif (
            result.classification == ReplyClassification.OBJECTION
            and result.confidence >= 0.85
            and result.suggested_response
        ):
            reply_subject = subject if subject and subject.lower().startswith("re:") else f"Re: {subject or 'your question'}"
            payload["auto_reply"] = await self.send_reply_email(
                lead_id, reply_subject, result.suggested_response,
            )

        elif result.should_escalate_voice:
            payload["voice_queue"] = await enqueue_voice_call(
                lead_id, reason=result.classification.value,
            )

        return payload

    def _interested_reply(self, lead: dict | None, affiliate_url: str) -> tuple[str, str]:
        name = (lead or {}).get("first_name") or "there"
        sender = settings.outbound_from_name
        body = (
            f"Hi {name},\n\n"
            "Great to hear you are interested.\n\n"
            f"Start free here (no credit card required):\n{affiliate_url}\n\n"
            "You can set up funnels, email, and your first offer in one place.\n\n"
            f"Best,\n{sender}"
        )
        return "Your free Systeme.io account link", body
