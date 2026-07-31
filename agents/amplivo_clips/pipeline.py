"""Amplivo Clips pipeline – scan → produce → QA → ready for submit."""

from __future__ import annotations

import time
from uuid import UUID

from packages.shared.clips import opus, store
from packages.shared.clips.models import QualityResult
from packages.shared.db import log_agent_run
from packages.shared.llm import generate_text, extract_json
from packages.shared.settings_store import get_runtime


class AmplivoClipsPipeline:
    name = "amplivo_clips"

    async def ingest_campaign(self, payload: dict) -> dict:
        campaign_id = await store.create_campaign(payload)
        await log_agent_run(
            self.name,
            input_summary=f"Ingest campaign {payload.get('title')}",
            output_summary=str(campaign_id),
        )
        return {"campaign_id": str(campaign_id)}

    async def scan_stub_campaigns(self, items: list[dict]) -> dict:
        """Normalize marketplace campaign dicts into DB (no browser yet)."""
        created = []
        for item in items:
            if not item.get("title") or not item.get("source_url"):
                continue
            cid = await store.create_campaign(
                {
                    "marketplace": item.get("marketplace") or "whop",
                    "external_id": item.get("external_id"),
                    "title": item["title"],
                    "source_url": item["source_url"],
                    "brief": item.get("brief"),
                    "payout_model": item.get("payout_model") or "cpm",
                    "payout_rate": item.get("payout_rate"),
                    "currency": item.get("currency") or "USD",
                    "metadata": item.get("metadata") or {},
                }
            )
            created.append(str(cid))
        return {"ingested": len(created), "campaign_ids": created}

    async def run_jobs(
        self,
        *,
        campaign_id: UUID | None = None,
        max_jobs: int = 3,
        dry_run: bool | None = None,
    ) -> dict:
        start = time.monotonic()
        if dry_run is None:
            dry_flag = (await get_runtime("clips_dry_run") or "true").lower()
            dry_run = dry_flag in {"1", "true", "yes"}

        if campaign_id:
            campaigns = [await store.get_campaign(campaign_id)]
            campaigns = [c for c in campaigns if c]
        else:
            campaigns = await store.list_open_campaigns(limit=max_jobs)

        results = []
        for campaign in campaigns[:max_jobs]:
            job_id = await store.create_job(campaign["id"])
            try:
                result = await self._produce_one(job_id, campaign, dry_run=dry_run)
                results.append(result)
            except Exception as exc:
                await store.update_job(job_id, status="failed", error_message=str(exc)[:500])
                results.append({"job_id": str(job_id), "status": "failed", "error": str(exc)})

        await log_agent_run(
            self.name,
            input_summary=f"run_jobs max={max_jobs}",
            output_summary=f"{len(results)} jobs",
            duration_ms=int((time.monotonic() - start) * 1000),
            metadata={"results": results},
        )
        return {"processed": len(results), "results": results, "dry_run": dry_run}

    async def _produce_one(self, job_id: UUID, campaign, *, dry_run: bool) -> dict:
        await store.update_job(job_id, status="producing")
        produced = await opus.create_project_from_url(campaign["source_url"], dry_run=dry_run)
        await store.update_job(
            job_id,
            status="qa",
            opus_project_id=produced.get("project_id"),
            clip_url=produced.get("clip_url"),
            metadata={"opus": produced.get("raw") or {}, "dry_run": produced.get("dry_run")},
        )

        qa = await self.quality_gate(
            title=campaign["title"],
            brief=campaign.get("brief") or "",
            source_url=campaign["source_url"],
            clip_url=produced.get("clip_url") or "",
            dry_run=bool(produced.get("dry_run")),
        )
        if not qa.accepted:
            await store.update_job(
                job_id,
                status="rejected",
                qa_score=qa.score,
                qa_notes=qa.notes,
            )
            return {"job_id": str(job_id), "status": "rejected", "qa": qa.model_dump()}

        await store.update_job(
            job_id,
            status="ready",
            qa_score=qa.score,
            qa_notes=qa.notes,
        )
        return {
            "job_id": str(job_id),
            "status": "ready",
            "clip_url": produced.get("clip_url"),
            "qa": qa.model_dump(),
            "dry_run": produced.get("dry_run"),
        }

    async def quality_gate(
        self,
        *,
        title: str,
        brief: str,
        source_url: str,
        clip_url: str,
        dry_run: bool,
    ) -> QualityResult:
        if dry_run:
            return QualityResult(accepted=True, score=75, notes="dry_run auto-accept")

        prompt = f"""Score this short-form clip candidate 0-100 for marketplace submission.
Return ONLY JSON: {{"accepted": bool, "score": int, "notes": str}}
Accept if score >= 65. Reject spam, weak hooks, unsafe content.

Campaign: {title}
Brief: {brief}
Source: {source_url}
Clip: {clip_url}
"""
        raw = await generate_text(prompt, "You QA short-form clips for streamer marketplaces.")
        data = extract_json(raw)
        return QualityResult(
            accepted=bool(data.get("accepted")),
            score=int(data.get("score") or 0),
            notes=str(data.get("notes") or "")[:400],
        )

    async def submit_job(
        self,
        job_id: UUID,
        *,
        post_url: str,
        proof_url: str | None = None,
        payout_amount: float | None = None,
    ) -> dict:
        job = await store.get_job(job_id)
        if not job:
            return {"ok": False, "reason": "not_found"}
        if job["status"] not in {"ready", "posted", "submitted"}:
            return {"ok": False, "reason": f"invalid_status:{job['status']}"}

        await store.update_job(
            job_id,
            status="submitted",
            post_url=post_url,
            proof_url=proof_url or post_url,
            payout_amount=payout_amount,
        )
        await log_agent_run(
            self.name,
            lead_id=None,
            input_summary=f"submit job {job_id}",
            output_summary=post_url,
        )
        return {"ok": True, "job_id": str(job_id), "status": "submitted"}
