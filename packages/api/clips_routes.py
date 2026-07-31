"""API routes for Amplivo Clips subsidiary."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.amplivo_clips.pipeline import AmplivoClipsPipeline
from packages.shared.clips import store
from packages.shared.clips.models import CampaignCreate, JobRunRequest, JobSubmitRequest

router = APIRouter(prefix="/clips", tags=["amplivo-clips"])
pipeline = AmplivoClipsPipeline()


class ScanRequest(BaseModel):
    campaigns: list[dict]


@router.get("/stats")
async def clips_stats():
    return await store.clip_stats()


@router.get("/campaigns")
async def clips_campaigns():
    rows = await store.list_open_campaigns(limit=50)
    return {
        "campaigns": [
            {
                "id": str(r["id"]),
                "marketplace": r["marketplace"],
                "title": r["title"],
                "source_url": r["source_url"],
                "payout_model": r["payout_model"],
                "payout_rate": float(r["payout_rate"]) if r["payout_rate"] is not None else None,
                "status": r["status"],
            }
            for r in rows
        ]
    }


@router.post("/campaigns")
async def create_campaign(req: CampaignCreate):
    result = await pipeline.ingest_campaign(req.model_dump())
    return {"ok": True, **result}


@router.post("/campaigns/scan")
async def scan_campaigns(req: ScanRequest):
    """Ingest normalized marketplace campaigns (browser scanner plugs in later)."""
    return await pipeline.scan_stub_campaigns(req.campaigns)


@router.get("/jobs")
async def list_jobs():
    rows = await store.list_jobs(limit=50)
    return {
        "jobs": [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "campaign_title": r["campaign_title"],
                "marketplace": r["marketplace"],
                "qa_score": r["qa_score"],
                "clip_url": r["clip_url"],
                "post_url": r["post_url"],
                "payout_amount": float(r["payout_amount"]) if r["payout_amount"] is not None else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.post("/jobs/run")
async def run_jobs(req: JobRunRequest = JobRunRequest()):
    return await pipeline.run_jobs(
        campaign_id=req.campaign_id,
        max_jobs=min(req.max_jobs, 10),
        dry_run=req.dry_run,
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
