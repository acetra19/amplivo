"""API routes for Amplivo Clips subsidiary."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.amplivo_clips.pipeline import AmplivoClipsPipeline
from packages.shared.clips import store
from packages.shared.clips.models import CampaignCreate, JobRunRequest, JobSubmitRequest
from packages.shared.settings_store import get_runtime

router = APIRouter(prefix="/clips", tags=["amplivo-clips"])
pipeline = AmplivoClipsPipeline()


class ScanRequest(BaseModel):
    campaigns: list[dict]


class DrainRequest(BaseModel):
    max_jobs: int | None = None
    auto_submit: bool | None = None
    force_auto_submit: bool = False


class MarkPaidRequest(BaseModel):
    payout_amount: float | None = None


class CampaignStatusRequest(BaseModel):
    status: str = "closed"


def _campaign_row(r) -> dict:
    return {
        "id": str(r["id"]),
        "marketplace": r["marketplace"],
        "external_id": r["external_id"],
        "title": r["title"],
        "source_url": r["source_url"],
        "brief": r["brief"],
        "payout_model": r["payout_model"],
        "payout_rate": float(r["payout_rate"]) if r["payout_rate"] is not None else None,
        "currency": r["currency"],
        "status": r["status"],
        "created_at": r["created_at"].isoformat(),
    }


def _job_row(r) -> dict:
    return {
        "id": str(r["id"]),
        "status": r["status"],
        "campaign_title": r.get("campaign_title"),
        "marketplace": r.get("marketplace"),
        "currency": r.get("currency") or "USD",
        "qa_score": r["qa_score"],
        "qa_notes": r.get("qa_notes"),
        "clip_url": r["clip_url"],
        "post_url": r["post_url"],
        "proof_url": r.get("proof_url"),
        "error_message": r.get("error_message"),
        "payout_amount": float(r["payout_amount"]) if r["payout_amount"] is not None else None,
        "created_at": r["created_at"].isoformat(),
    }


async def _runtime_flags() -> dict:
    dry = (await get_runtime("clips_dry_run") or "true").lower() in {"1", "true", "yes"}
    return {
        "dry_run": dry,
        "max_jobs_per_run": await get_runtime("clips_max_jobs_per_run") or "3",
        "default_marketplace": await get_runtime("clips_default_marketplace") or "whop",
        "opusclip_configured": bool(await get_runtime("opusclip_api_key")),
    }


@router.get("/overview")
async def clips_overview():
    stats = await store.clip_stats()
    campaigns = await store.list_campaigns(limit=40)
    jobs = await store.list_jobs(limit=40)
    return {
        "stats": stats,
        "campaigns": [_campaign_row(r) for r in campaigns],
        "jobs": [_job_row(r) for r in jobs],
        "runtime": await _runtime_flags(),
        "automation": {
            "seed_demos": "POST /clips/campaigns/seed",
            "drain": "POST /clips/drain",
            "run": "POST /clips/jobs/run",
            "poll": "POST /clips/jobs/poll",
            "auto_submit": "POST /clips/jobs/auto-submit",
        },
    }


@router.get("/stats")
async def clips_stats():
    stats = await store.clip_stats()
    stats["runtime"] = await _runtime_flags()
    return stats


@router.get("/campaigns")
async def clips_campaigns():
    rows = await store.list_campaigns(limit=50)
    return {"campaigns": [_campaign_row(r) for r in rows]}


@router.post("/campaigns")
async def create_campaign(req: CampaignCreate):
    result = await pipeline.ingest_campaign(req.model_dump())
    return {"ok": True, **result}


@router.post("/campaigns/scan")
async def scan_campaigns(req: ScanRequest):
    return await pipeline.scan_stub_campaigns(req.campaigns)


@router.post("/campaigns/seed")
async def seed_campaigns():
    return await pipeline.seed_demo_campaigns()


@router.post("/campaigns/{campaign_id}/status")
async def set_campaign_status(campaign_id: UUID, req: CampaignStatusRequest):
    if req.status not in {"open", "closed", "paused"}:
        raise HTTPException(status_code=400, detail="invalid status")
    await store.set_campaign_status(campaign_id, req.status)
    return {"ok": True, "campaign_id": str(campaign_id), "status": req.status}


@router.get("/jobs")
async def list_jobs():
    rows = await store.list_jobs(limit=50)
    return {"jobs": [_job_row(r) for r in rows]}


@router.post("/jobs/run")
async def run_jobs(req: JobRunRequest = JobRunRequest()):
    return await pipeline.run_jobs(
        campaign_id=req.campaign_id,
        max_jobs=req.max_jobs,
        dry_run=req.dry_run,
        force=req.force,
    )


@router.post("/jobs/poll")
async def poll_jobs(limit: int = 5):
    return await pipeline.poll_producing_jobs(limit=min(limit, 20))


@router.post("/jobs/auto-submit")
async def auto_submit(limit: int = 10, force: bool = False):
    return await pipeline.auto_submit_ready(limit=min(limit, 20), force=force)


@router.post("/drain")
async def drain(req: DrainRequest = DrainRequest()):
    return await pipeline.drain(
        max_jobs=req.max_jobs,
        auto_submit=req.auto_submit,
        force_auto_submit=req.force_auto_submit,
    )


@router.post("/jobs/{job_id}/submit")
async def submit_job(job_id: UUID, req: JobSubmitRequest):
    result = await pipeline.submit_job(
        job_id,
        post_url=req.post_url,
        proof_url=req.proof_url,
        payout_amount=req.payout_amount,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("reason"))
    return result


@router.post("/jobs/{job_id}/paid")
async def mark_paid(job_id: UUID, req: MarkPaidRequest = MarkPaidRequest()):
    result = await pipeline.mark_paid(job_id, payout_amount=req.payout_amount)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("reason"))
    return result
