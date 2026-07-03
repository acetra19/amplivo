"""Shared types and data models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LeadStatus(str, Enum):
    NEW = "new"
    ENRICHED = "enriched"
    CONTACTED = "contacted"
    REPLIED = "replied"
    QUALIFIED = "qualified"
    TRIAL_STARTED = "trial_started"
    CONVERTED = "converted"
    LOST = "lost"
    UNSUBSCRIBED = "unsubscribed"


class InteractionChannel(str, Enum):
    EMAIL = "email"
    CHAT = "chat"
    VOICE = "voice"
    SMS = "sms"
    LINKEDIN = "linkedin"


class LeadCreate(BaseModel):
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    job_title: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    website: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    country: str = "DE"
    source: str | None = None
    utm_source: str | None = None
    utm_campaign: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LeadResponse(BaseModel):
    id: UUID
    email: str
    first_name: str | None
    company: str | None
    status: LeadStatus
    score: int
    icp_match: bool
    created_at: datetime


class LeadScoreResult(BaseModel):
    score: int = Field(ge=0, le=100)
    icp_match: bool
    reasoning: str
    recommended_sequence: str


class ReplyClassification(str, Enum):
    INTERESTED = "interested"
    OBJECTION = "objection"
    NOT_NOW = "not_now"
    UNSUBSCRIBE = "unsubscribe"
    OOO = "out_of_office"
    OTHER = "other"


class ClassifiedReply(BaseModel):
    classification: ReplyClassification
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    suggested_response: str | None = None
    should_escalate_voice: bool = False


class AgentRunResult(BaseModel):
    agent_name: str
    success: bool
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)
