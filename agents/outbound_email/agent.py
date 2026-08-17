"""Outbound email agent – scores leads, personalizes sequences, sends via Brevo."""

from __future__ import annotations

import json
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
    pause_sequences_for_lead,
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


def _normalize_reply_classification(raw: str) -> str:
    value = raw.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "ooo": "out_of_office",
        "out_of_office": "out_of_office",
        "not_now": "not_now",
        "notnow": "not_now",
        "interested": "interested",
        "objection": "objection",
        "unsubscribe": "unsubscribe",
        "other": "other",
    }
    return aliases.get(value, value)


def _parse_classified_reply(raw: str, reply_body: str) -> ClassifiedReply:
    try:
        data = extract_json(raw)
    except json.JSONDecodeError:
        lowered = reply_body.lower()
        if any(word in lowered for word in ("unsubscribe", "remove me", "stop emailing", " stop", "stop.", "abmelden")):
            fallback = "unsubscribe"
        elif any(word in lowered for word in ("interested", "send link", "free link", "yes please", "sign me up")):
            fallback = "interested"
        else:
            fallback = "other"
        return ClassifiedReply(
            classification=ReplyClassification(fallback),
            confidence=0.6,
            summary="Fallback classification due to invalid LLM JSON",
            suggested_response=None,
            should_escalate_voice=fallback == "interested",
        )

    if isinstance(data.get("classification"), str):
        data["classification"] = _normalize_reply_classification(data["classification"])
    if "confidence" in data:
        data["confidence"] = float(data["confidence"])
    return ClassifiedReply(**data)


def _heuristic_score(lead: dict) -> LeadScoreResult:
    """Fallback when LLM scoring is unavailable — keep pipeline moving."""
    industry = (lead.get("industry") or "").lower()
    country = (lead.get("country") or "").upper()
    email = (lead.get("email") or "").lower()
    local = email.split("@", 1)[0] if "@" in email else ""
    employees = lead.get("employee_count") or 1

    score = 40
    if industry in {"online_business", "coaching", "marketing_agency", "education"}:
        score += 25
    if country in {"DE", "AT", "CH"}:
        score += 10
    if 1 <= int(employees) <= 20:
        score += 10
    if local and local not in {
        "info", "contact", "kontakt", "hello", "hallo", "office", "mail", "team",
    }:
        score += 10
    score = max(0, min(100, score))
    icp = score >= 55
    return LeadScoreResult(
        score=score,
        icp_match=icp,
        reasoning="Heuristic score (LLM unavailable)",
        recommended_sequence="outbound_a" if score >= 70 else "nurture_b",
    )


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

        try:
            raw = await classify_text(prompt, SCORE_SYSTEM)
            data = extract_json(raw)
            result = LeadScoreResult(**data)
        except Exception:
            result = _heuristic_score(dict(lead))

        # Never downgrade pipeline status on re-score (discover re-imports contacts)
        current = lead.get("status")
        protected = {
            "contacted", "replied", "qualified", "trial_started",
            "converted", "lost", "unsubscribed",
        }
        if current in protected:
            status = None
        else:
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

        affiliate_url = await get_affiliate_url(lead_id)
        personalized = await self.personalize_email(
            lead_id, step["subject_tpl"], step["body_tpl"], affiliate_url=affiliate_url,
        )
        if not (personalized.get("subject") or "").strip() or not (personalized.get("body") or "").strip():
            return {"skipped": True, "reason": "empty_personalized_email"}

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
                results.append(
                    {
                        "lead_id": str(item["lead_id"]),
                        "email": item.get("email"),
                        **result,
                    }
                )
                if result.get("skipped") and result.get("reason") == "daily_limit_reached":
                    break
            except BrevoError as exc:
                results.append(
                    {
                        "lead_id": str(item["lead_id"]),
                        "email": item.get("email"),
                        "error": str(exc),
                    }
                )
                break
            except Exception as exc:
                results.append(
                    {
                        "lead_id": str(item["lead_id"]),
                        "email": item.get("email"),
                        "skipped": True,
                        "reason": f"send_failed:{type(exc).__name__}:{exc}",
                    }
                )
                continue
        return {
            "processed": sum(1 for r in results if r.get("sent")),
            "results": results,
            "remaining_quota": await remaining_quota(),
        }

    async def send_reply_email(
        self,
        lead_id: UUID,
        subject: str,
        body: str,
        *,
        count_toward_quota: bool = False,
    ) -> dict:
        """Send a one-off reply (e.g. interested link / objection) via Brevo."""
        lead = await get_lead_by_id(lead_id)
        if not lead or lead["do_not_contact"]:
            return {"skipped": True, "reason": "do_not_contact"}
        if count_toward_quota and not await can_send():
            return {"skipped": True, "reason": "daily_limit_reached"}

        await send_email(lead["email"], subject, body, to_name=lead["first_name"])
        await log_interaction(
            lead_id, channel="email", direction="outbound",
            subject=subject, body=body, agent_name=self.name,
            metadata={"kind": "auto_reply", "counts_quota": count_toward_quota},
        )
        gamification = await award_xp("email_sent", f"Reply to {lead['email']}")
        return {"sent": True, "remaining_quota": await remaining_quota(), "gamification": gamification}

    async def personalize_email(
        self,
        lead_id: UUID,
        subject_tpl: str,
        body_tpl: str,
        *,
        affiliate_url: str | None = None,
    ) -> dict[str, str]:
        lead = await get_lead_by_id(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        country = (lead.get("country") or "DE").upper()
        language = "German" if country in {"DE", "AT", "CH"} else "English"
        url = affiliate_url or ""
        sender = await get_runtime("outbound_from_name") or settings.outbound_from_name
        subject = subject_tpl.replace("{{first_name}}", lead.get("first_name") or "there")
        subject = subject.replace("{{company}}", lead.get("company") or "your business")
        subject = subject.replace("{{industry}}", lead.get("industry") or "online business")
        body = body_tpl.replace("{{first_name}}", lead.get("first_name") or "there")
        body = body.replace("{{company}}", lead.get("company") or "your business")
        body = body.replace("{{industry}}", lead.get("industry") or "online business")
        body = body.replace("{{sender_name}}", sender)
        body = body.replace("{{affiliate_url}}", url)

        template_has_url = bool(url) and url in body
        fallback = {"subject": subject, "body": body}

        prompt = f"""Personalize this cold email for the lead. Write in {language}.
Keep it concise, human, and professional — not salesy.
Preserve EVERY URL exactly as written if present. Do not invent product or affiliate links.
If the template has no URL, do NOT add any link.
Keep the STOP / unsubscribe P.S. if present. Do not invent facts about the lead.
Prefer one clear question over a pitch. Mention Systeme.io only if the template already does.
Return JSON: {{"subject": str, "body": str}}

Lead: {dict(lead)}
Template subject: {subject}
Template body: {body}
Sender name: {sender}"""

        try:
            raw = await generate_text(
                prompt,
                "You write short, curious B2B cold emails that earn replies.",
            )
            result = extract_json(raw)
        except Exception:
            return fallback

        out_subject = (result.get("subject") or "").strip()
        out_body = (result.get("body") or "").strip()
        if not out_subject or not out_body:
            return fallback

        # Only re-inject affiliate URL when the template already contained it
        if template_has_url and url and url not in out_body:
            out_body = out_body.rstrip() + f"\n\n{url}\n"
        return {"subject": out_subject, "body": out_body}

    async def classify_reply(self, lead_id: UUID, reply_body: str) -> ClassifiedReply:
        start = time.monotonic()
        lead = await get_lead_by_id(lead_id)

        prompt = f"""Classify this email reply.

Original lead: {lead['email']}, {lead['company']}
Reply:
{reply_body}"""

        raw = await classify_text(prompt, REPLY_SYSTEM)
        result = _parse_classified_reply(raw, reply_body)

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
        try:
            result = await self.classify_reply(lead_id, reply_body)
        except Exception as exc:
            return {
                "classification": "error",
                "summary": str(exc),
                "auto_reply": None,
                "auto_reply_error": str(exc),
            }

        payload = result.model_dump()
        payload["auto_reply"] = None
        payload["auto_reply_error"] = None

        await pause_sequences_for_lead(lead_id)

        try:
            if result.classification == ReplyClassification.INTERESTED:
                affiliate_url = await get_affiliate_url(lead_id)
                if affiliate_url:
                    lead = await get_lead_by_id(lead_id)
                    subj, body = self._interested_reply(lead, affiliate_url)
                    payload["auto_reply"] = await self.send_reply_email(lead_id, subj, body)
                else:
                    payload["auto_reply_error"] = "affiliate_url_not_configured"
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
                reply_subject = (
                    subject if subject and subject.lower().startswith("re:")
                    else f"Re: {subject or 'your question'}"
                )
                payload["auto_reply"] = await self.send_reply_email(
                    lead_id, reply_subject, result.suggested_response,
                )

            elif result.should_escalate_voice:
                payload["voice_queue"] = await enqueue_voice_call(
                    lead_id, reason=result.classification.value,
                )
        except BrevoError as exc:
            payload["auto_reply_error"] = str(exc)

        return payload

    def _interested_reply(self, lead: dict | None, affiliate_url: str) -> tuple[str, str]:
        name = (lead or {}).get("first_name") or "there"
        sender = settings.outbound_from_name
        country = ((lead or {}).get("country") or "DE").upper()
        if country in {"DE", "AT", "CH"}:
            body = (
                f"Hallo {name},\n\n"
                "super, dass du Interesse hast.\n\n"
                f"Hier ist dein kostenloser Zugang (ohne Kreditkarte):\n{affiliate_url}\n\n"
                "Naechste Schritte:\n"
                "1) Account anlegen\n"
                "2) Ein Funnel-Template waehlen\n"
                "3) Erste E-Mail / Angebot verbinden\n\n"
                "Wenn du haengst, antworte einfach auf diese Mail.\n\n"
                f"Beste Gruesse\n{sender}"
            )
            return "Dein kostenloser Systeme.io Zugang", body

        body = (
            f"Hi {name},\n\n"
            "Great to hear you are interested.\n\n"
            f"Start free here (no credit card required):\n{affiliate_url}\n\n"
            "Next steps:\n"
            "1) Create your account\n"
            "2) Pick a funnel template\n"
            "3) Connect your first email / offer\n\n"
            "Reply if you get stuck — happy to help.\n\n"
            f"Best,\n{sender}"
        )
        return "Your free Systeme.io account link", body
