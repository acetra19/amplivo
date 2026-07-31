"""Pydantic models for Amplivo Clips."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class CampaignCreate(BaseModel):
    marketplace: str = "manual"
    external_id: str | None = None
    title: str
    source_url: str
    brief: str | None = None
    payout_model: str = "cpm"
    payout_rate: float | None = None
    currency: str = "USD"
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobRunRequest(BaseModel):
    campaign_id: UUID | None = None
    max_jobs: int | None = None
    dry_run: bool | None = None
    force: bool = False


class JobSubmitRequest(BaseModel):
    post_url: str
    proof_url: str | None = None
    payout_amount: float | None = None


class QualityResult(BaseModel):
    accepted: bool
    score: int = Field(ge=0, le=100)
    notes: str = ""
