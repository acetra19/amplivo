"""Website chat qualifier agent – BANT scoring via conversational flow."""

from __future__ import annotations

import time
from uuid import UUID

from packages.shared.config import settings
from packages.shared.settings_store import get_runtime
from packages.shared.db import get_connection
from packages.shared.gamification import award_xp
from packages.shared.knowledge import format_knowledge_context, search_knowledge
from packages.shared.llm import extract_json, generate_text


QUALIFIER_SYSTEM = """You are a B2B sales qualification chatbot for an affiliate product demo.
Goals: understand pain points, budget signals, timeline, decision authority (BANT-lite).
Be helpful, concise, in English. Never be pushy.
If the visitor shows strong fit, suggest starting a free trial.

After each turn, append a hidden JSON block on a new line:
---SCORE---
{"score": int, "icp_match": bool, "reasoning": str, "ready_for_trial": bool}
Only include score block in your response, user sees only the conversational part before ---SCORE---"""


class QualifierChatAgent:
    name = "qualifier_chat"

    async def respond(self, lead_id: UUID, message: str, history: list[dict] | None = None) -> dict:
        start = time.monotonic()
        lead = await get_lead_by_id(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        history = history or []
        context = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])

        chunks = await search_knowledge(message)
        product_docs = format_knowledge_context(chunks)

        product = await get_runtime("affiliate_product_slug") or settings.affiliate_product_slug
        threshold = int(await get_runtime("lead_score_threshold") or settings.lead_score_threshold)
        affiliate_url = await get_runtime("affiliate_tracking_base") or None

        prompt = f"""Product: {product}
Lead: {lead['email']}, {lead['company']}, {lead['job_title']}

Product knowledge (use for accurate answers):
{product_docs}

Conversation so far:
{context}

Visitor message: {message}"""

        raw = await generate_text(prompt, QUALIFIER_SYSTEM)

        if "---SCORE---" in raw:
            visible, score_part = raw.split("---SCORE---", 1)
            score_data = extract_json(score_part.strip())
        else:
            visible = raw
            score_data = {"score": 0, "icp_match": False, "reasoning": "No score", "ready_for_trial": False}

        await log_interaction(
            lead_id, channel="chat", direction="inbound",
            body=message, agent_name=self.name,
        )
        await log_interaction(
            lead_id, channel="chat", direction="outbound",
            body=visible.strip(), agent_name=self.name,
        )

        if score_data.get("score", 0) >= threshold:
            await update_lead_score(
                lead_id, score_data["score"], score_data.get("icp_match", False), "qualified",
            )
            await award_xp("lead_qualified", f"Chat qualified: {lead['email']}")

        await log_agent_run(
            self.name,
            lead_id=lead_id,
            input_summary=message[:200],
            output_summary=f"Score={score_data.get('score', 0)}",
            duration_ms=int((time.monotonic() - start) * 1000),
            metadata=score_data,
        )

        return {
            "reply": visible.strip(),
            "score": score_data.get("score", 0),
            "ready_for_trial": score_data.get("ready_for_trial", False),
            "affiliate_url": affiliate_url,
        }
