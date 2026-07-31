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

    async def _is_dry_run(self, override: bool | None = None) -> bool:
        if override is not None:
            return override
        flag = (await get_runtime("clips_dry_run") or "true").lower()
        return flag in {"1", "true", "yes"}

    async def _max_jobs(self, requested: int | None = None) -> int:
        if requested is not None:
            return max(1, min(int(requested), 10))
        raw = await get_runtime("clips_max_jobs_per_run")
        try:
            n = int(raw or 3)
        except (TypeError, ValueError):
            n = 3
        return max(1, min(n, 10))

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
        default_market = (await get_runtime("clips_default_marketplace")) or "whop"
        for item in items:
            if not item.get("title") or not item.get("source_url"):
                continue
            cid = await store.create_campaign(
                {
                    "marketplace": item.get("marketplace") or default_market,
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
        max_jobs: int | None = None,
        dry_run: bool | None = None,
        force: bool = False,
    ) -> dict:
        start = time.monotonic()
        dry_run = await self._is_dry_run(dry_run)
        limit = await self._max_jobs(max_jobs)

        # Finish any Opus projects waiting on clips first.
        polled = await self.poll_producing_jobs(limit=limit)

        if campaign_id:
            campaign = await store.get_campaign(campaign_id)
            campaigns = [campaign] if campaign else []
            if campaigns and not force and await store.campaign_has_blocking_job(campaign_id):
                return {
                    "processed": 0,
                    "skipped": "campaign_has_active_job",
                    "results": [],
                    "polled": polled,
                    "dry_run": dry_run,
                }
        else:
            campaigns = await store.list_workable_campaigns(limit=limit)

        results = []
        for campaign in campaigns[:limit]:
            job_id = await store.create_job(campaign["id"])
            try:
                result = await self._produce_one(job_id, campaign, dry_run=dry_run)
                results.append(result)
            except Exception as exc:
                await store.update_job(job_id, status="failed", error_message=str(exc)[:500])
                results.append({"job_id": str(job_id), "status": "failed", "error": str(exc)})

        await log_agent_run(
            self.name,
            input_summary=f"run_jobs max={limit}",
            output_summary=f"{len(results)} jobs, polled={polled.get('checked', 0)}",
            duration_ms=int((time.monotonic() - start) * 1000),
            metadata={"results": results, "polled": polled},
        )
        return {
            "processed": len(results),
            "results": results,
            "polled": polled,
            "dry_run": dry_run,
        }

    async def poll_producing_jobs(self, *, limit: int = 5) -> dict:
        jobs = await store.list_producing_jobs(limit=limit)
        advanced = []
        for job in jobs:
            project_id = job.get("opus_project_id")
            if not project_id:
                continue
            try:
                produced = await opus.fetch_exportable_clips(str(project_id))
            except Exception as exc:
                advanced.append({"job_id": str(job["id"]), "status": "producing", "error": str(exc)})
                continue
            if not produced.get("clip_url"):
                advanced.append({"job_id": str(job["id"]), "status": "producing"})
                continue
            campaign = {
                "title": job.get("campaign_title") or "",
                "brief": job.get("brief") or "",
                "source_url": job.get("source_url") or "",
            }
            await store.update_job(
                job["id"],
                status="qa",
                clip_url=produced.get("clip_url"),
                metadata={"opus": produced.get("raw") or {}, "dry_run": produced.get("dry_run")},
            )
            qa = await self.quality_gate(
                title=campaign["title"],
                brief=campaign["brief"],
                source_url=campaign["source_url"],
                clip_url=produced.get("clip_url") or "",
                dry_run=bool(produced.get("dry_run")),
            )
            if not qa.accepted:
                await store.update_job(
                    job["id"], status="rejected", qa_score=qa.score, qa_notes=qa.notes
                )
                advanced.append({"job_id": str(job["id"]), "status": "rejected"})
                continue
            await store.update_job(
                job["id"], status="ready", qa_score=qa.score, qa_notes=qa.notes
            )
            advanced.append({"job_id": str(job["id"]), "status": "ready"})
        return {"checked": len(jobs), "advanced": advanced}

    async def _produce_one(self, job_id: UUID, campaign, *, dry_run: bool) -> dict:
        await store.update_job(job_id, status="producing")
        produced = await opus.create_project_from_url(campaign["source_url"], dry_run=dry_run)

        # Live Opus is async — short wait, then leave producing for later drain poll.
        if not produced.get("dry_run") and not produced.get("clip_url") and produced.get("project_id"):
            produced = await opus.wait_for_clip(produced["project_id"], attempts=2, delay_sec=6.0)

        await store.update_job(
            job_id,
            opus_project_id=produced.get("project_id"),
            clip_url=produced.get("clip_url"),
            metadata={"opus": produced.get("raw") or {}, "dry_run": produced.get("dry_run")},
        )

        if not produced.get("clip_url"):
            await store.update_job(job_id, status="producing")
            return {
                "job_id": str(job_id),
                "status": "producing",
                "project_id": produced.get("project_id"),
                "dry_run": produced.get("dry_run"),
            }

        await store.update_job(job_id, status="qa")
        qa = await self.quality_gate(
            title=campaign["title"],
            brief=campaign.get("brief") or "",
            source_url=campaign["source_url"],
            clip_url=produced.get("clip_url") or "",
            dry_run=bool(produced.get("dry_run")),
        )
        if not qa.accepted:
            await store.update_job(
                job_id, status="rejected", qa_score=qa.score, qa_notes=qa.notes
            )
            return {"job_id": str(job_id), "status": "rejected", "qa": qa.model_dump()}

        await store.update_job(
            job_id, status="ready", qa_score=qa.score, qa_notes=qa.notes
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
        if job["status"] not in {"ready", "posted"}:
            return {"ok": False, "reason": f"invalid_status:{job['status']}"}

        amount = payout_amount
        if amount is None and job.get("payout_rate") is not None:
            amount = float(job["payout_rate"])

        await store.update_job(
            job_id,
            status="submitted",
            post_url=post_url,
            proof_url=proof_url or post_url,
            payout_amount=amount,
        )
        await log_agent_run(
            self.name,
            lead_id=None,
            input_summary=f"submit job {job_id}",
            output_summary=post_url,
        )
        return {"ok": True, "job_id": str(job_id), "status": "submitted", "payout_amount": amount}

    async def seed_demo_campaigns(self) -> dict:
        """Public sample sources so the GUI/pipeline can be exercised end-to-end."""
        demos = [
            {
                "marketplace": "demo",
                "external_id": "demo-yt-1",
                "title": "Demo: Gaming highlight reel",
                "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "brief": "Extract 1 hooky 30-45s short with captions.",
                "payout_model": "cpm",
                "payout_rate": 2.0,
            },
            {
                "marketplace": "demo",
                "external_id": "demo-yt-2",
                "title": "Demo: Creator talk clip",
                "source_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                "brief": "Find the punchiest quote moment.",
                "payout_model": "flat",
                "payout_rate": 15.0,
            },
            {
                "marketplace": "whop",
                "external_id": "seed-placeholder-1",
                "title": "Placeholder Whop campaign (replace source)",
                "source_url": "https://www.youtube.com/watch?v=9bZkp7q19f0",
                "brief": "Replace with real campaign VOD once Whop is connected.",
                "payout_model": "cpm",
                "payout_rate": 3.0,
            },
        ]
        return await self.scan_stub_campaigns(demos)

    async def auto_submit_ready(self, *, limit: int = 10, force: bool = False) -> dict:
        """Synthetic proof submit — only safe in dry-run unless force=True."""
        dry = await self._is_dry_run()
        if not dry and not force:
            return {
                "submitted": 0,
                "skipped": "auto_submit_requires_dry_run_or_force",
                "results": [],
            }
        ready = await store.list_jobs_by_status("ready", limit=limit)
        submitted = []
        for job in ready:
            post_url = f"https://proof.amplivo.net/clips/{job['id']}"
            result = await self.submit_job(
                job["id"],
                post_url=post_url,
                proof_url=post_url,
                payout_amount=None,
            )
            submitted.append(result)
        return {"submitted": len(submitted), "results": submitted, "dry_run": dry}

    async def mark_paid(self, job_id: UUID, payout_amount: float | None = None) -> dict:
        job = await store.get_job(job_id)
        if not job:
            return {"ok": False, "reason": "not_found"}
        if job["status"] != "submitted":
            return {"ok": False, "reason": f"invalid_status:{job['status']}"}
        amount = payout_amount
        if amount is None and job.get("payout_amount") is not None:
            amount = float(job["payout_amount"])
        elif amount is None and job.get("payout_rate") is not None:
            amount = float(job["payout_rate"])
        await store.update_job(job_id, status="paid", payout_amount=amount)
        return {"ok": True, "job_id": str(job_id), "status": "paid", "payout_amount": amount}

    async def drain(
        self,
        *,
        max_jobs: int | None = None,
        auto_submit: bool | None = None,
        force_auto_submit: bool = False,
    ) -> dict:
        """Agent cycle: poll producing → produce workable → optional dry-run auto-submit."""
        dry = await self._is_dry_run()
        limit = await self._max_jobs(max_jobs)
        run = await self.run_jobs(max_jobs=limit, dry_run=dry)

        do_submit = auto_submit if auto_submit is not None else dry
        submit: dict = {"submitted": 0, "results": [], "skipped": None}
        if do_submit:
            submit = await self.auto_submit_ready(limit=limit, force=force_auto_submit or False)
        elif auto_submit is False:
            submit = {"submitted": 0, "results": [], "skipped": "auto_submit_disabled"}
        else:
            submit = {"submitted": 0, "results": [], "skipped": "live_mode_no_fake_proofs"}

        stats = await store.clip_stats()
        return {"run": run, "submit": submit, "stats": stats, "dry_run": dry}
