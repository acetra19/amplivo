"""FastAPI gateway – webhooks for n8n, chat widget, affiliate postbacks."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

from agents.outbound_email.agent import OutboundEmailAgent
from agents.ops_reporter.agent import OpsReporterAgent
from agents.qualifier_chat.agent import QualifierChatAgent
from packages.shared.config import settings
from packages.shared.db import get_connection, get_lead_by_email, get_lead_by_id, upsert_lead
from packages.api.settings_routes import router as settings_router
from packages.shared.gamification import award_xp, get_dashboard_state
from packages.shared.models import LeadCreate
from packages.shared.queue import dequeue_voice_call, enqueue_voice_call, ping_redis, voice_queue_length
from packages.shared.stats import get_pipeline_stats

LANDING_DIR = Path(__file__).resolve().parents[2] / "landing"
DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "dashboard"
WELCOME_MESSAGE = (
    "Hi! I am your sales assistant. I can answer questions about the platform, "
    "pricing, and whether it fits your agency. What would you like to know?"
)


async def seed_settings_from_env() -> None:
    """Import .env values into DB on first run (one-time per key)."""
    from packages.shared.settings_store import SETTING_FIELDS, _env_fallback

    async with get_connection() as conn:
        for key in SETTING_FIELDS:
            row = await conn.fetchrow("SELECT value FROM app_settings WHERE key = $1", key)
            if row and row["value"]:
                continue
            val = _env_fallback(key)
            if val:
                await conn.execute("UPDATE app_settings SET value = $1 WHERE key = $2", val, key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from packages.shared.schema_bootstrap import ensure_app_schema

    try:
        await ensure_app_schema()
        await seed_settings_from_env()
    except Exception:
        pass
    app.state.outbound = OutboundEmailAgent()
    app.state.qualifier = QualifierChatAgent()
    app.state.ops = OpsReporterAgent()
    yield


app = FastAPI(title="Amplivo API", version="0.3.0", lifespan=lifespan)
app.include_router(settings_router)

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if (LANDING_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=LANDING_DIR / "assets"), name="landing-assets")

if (DASHBOARD_DIR / "assets").is_dir():
    app.mount("/dashboard/assets", StaticFiles(directory=DASHBOARD_DIR / "assets"), name="dashboard-assets")


@app.get("/health")
async def health():
    db_ok = False
    try:
        async with get_connection() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "redis": await ping_redis(),
        "version": "0.3.0",
    }


@app.get("/dashboard")
async def dashboard_page():
    index = DASHBOARD_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Dashboard not found")


@app.get("/dashboard/settings")
async def dashboard_settings_page():
    page = DASHBOARD_DIR / "settings.html"
    if page.is_file():
        return FileResponse(page)
    raise HTTPException(status_code=404, detail="Settings page not found")


@app.get("/dashboard/state")
async def dashboard_state():
    return await get_dashboard_state()


@app.get("/")
async def landing_page():
    index = LANDING_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"message": "Agentic Sales Agency API", "docs": "/docs"}


@app.get("/pipeline/stats")
async def pipeline_stats():
    return await get_pipeline_stats()


@app.post("/leads")
async def create_lead(lead: LeadCreate):
    lead_id = await upsert_lead(lead.model_dump())
    score = await app.state.outbound.score_lead(lead_id)
    xp = await award_xp("lead_created", f"Lead: {lead.email}")
    if score.icp_match:
        xp_icp = await award_xp("lead_icp_match", f"ICP match: {lead.email}")
        xp["icp_bonus"] = xp_icp
    return {"lead_id": str(lead_id), "score": score.model_dump(), "gamification": xp}


class RegisterRequest(BaseModel):
    email: EmailStr
    first_name: str | None = None
    company: str | None = None
    industry: str = "marketing_agency"
    source: str = "landing"


@app.post("/register")
async def register_visitor(req: RegisterRequest):
    lead_id = await upsert_lead(req.model_dump())
    score_result = await app.state.outbound.score_lead(lead_id)
    affiliate_url = await get_runtime("affiliate_tracking_base") or None
    product_slug = await get_runtime("affiliate_product_slug") or settings.affiliate_product_slug
    if not affiliate_url:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """SELECT affiliate_url FROM affiliate_products
                   WHERE slug = $1 AND is_active = true""",
                product_slug,
            )
            if row:
                affiliate_url = row["affiliate_url"]
                if "YOUR-AFFILIATE" in affiliate_url:
                    affiliate_url = None

    return {
        "lead_id": str(lead_id),
        "score": score_result.score,
        "icp_match": score_result.icp_match,
        "affiliate_url": affiliate_url,
        "welcome_message": WELCOME_MESSAGE,
        "gamification": await award_xp("lead_created", f"Landing signup: {req.email}"),
    }


class ChatRequest(BaseModel):
    lead_id: UUID
    message: str
    history: list[dict] | None = None


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        return await app.state.qualifier.respond(req.lead_id, req.message, req.history)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class ReplyWebhook(BaseModel):
    lead_id: UUID
    body: str


@app.post("/webhooks/email-reply")
async def email_reply(req: ReplyWebhook):
    result = await app.state.outbound.classify_reply(req.lead_id, req.body)
    payload = result.model_dump()
    if result.should_escalate_voice or result.classification.value == "interested":
        queue = await enqueue_voice_call(req.lead_id, reason=result.classification.value)
        payload["voice_queue"] = queue
    return payload


class VoiceQueueRequest(BaseModel):
    lead_id: UUID
    reason: str = "interested"


@app.post("/webhooks/voice-queue")
async def voice_queue_add(req: VoiceQueueRequest):
    return await enqueue_voice_call(req.lead_id, req.reason)


@app.get("/webhooks/voice-queue")
async def voice_queue_list():
    return {"queue_length": await voice_queue_length()}


@app.post("/webhooks/voice-queue/dequeue")
async def voice_queue_pop():
    item = await dequeue_voice_call()
    if not item:
        return {"item": None}
    lead = await get_lead_by_id(UUID(item["lead_id"]))
    return {"item": item, "lead": dict(lead) if lead else None}


class AffiliatePostback(BaseModel):
    email: EmailStr | None = None
    lead_id: UUID | None = None
    event_type: str
    affiliate_tx_id: str | None = None
    commission_amount: float | None = None


class OutboundSendRequest(BaseModel):
    lead_id: UUID
    sequence: str = "outbound_a"
    step: int = 1


class OutboundReplyRequest(BaseModel):
    lead_id: UUID
    subject: str
    body: str


class BrevoInboundWebhook(BaseModel):
    from_email: EmailStr
    subject: str | None = None
    text: str | None = None
    html: str | None = None


@app.post("/outbound/send")
async def outbound_send(req: OutboundSendRequest):
    result = await app.state.outbound.send_sequence_step(req.lead_id, req.sequence, req.step)
    if result.get("skipped") and result.get("reason") == "daily_limit_reached":
        raise HTTPException(status_code=429, detail="Daily email limit reached")
    return result


@app.post("/outbound/process-queue")
async def outbound_process_queue():
    return await app.state.outbound.process_followup_queue()


@app.get("/outbound/stats")
async def outbound_stats():
    from packages.shared.rate_limit import get_today_sent_count, remaining_quota, _daily_limit

    sent = await get_today_sent_count()
    limit = await _daily_limit()
    return {
        "sent_today": sent,
        "daily_limit": limit,
        "remaining": await remaining_quota(),
    }


@app.post("/outbound/reply")
async def outbound_reply(req: OutboundReplyRequest):
    result = await app.state.outbound.send_reply_email(req.lead_id, req.subject, req.body)
    if result.get("skipped") and result.get("reason") == "daily_limit_reached":
        raise HTTPException(status_code=429, detail="Daily email limit reached")
    return result


@app.post("/webhooks/brevo-inbound")
async def brevo_inbound(payload: BrevoInboundWebhook):
    lead = await get_lead_by_email(payload.from_email)
    if not lead:
        return {"ok": False, "reason": "unknown_sender"}

    body = payload.text or payload.html or ""
    result = await app.state.outbound.classify_reply(lead["id"], body)
    data = result.model_dump()
    if result.should_escalate_voice or result.classification.value == "interested":
        data["voice_queue"] = await enqueue_voice_call(lead["id"], reason=result.classification.value)
    return data


@app.post("/webhooks/affiliate")
async def affiliate_postback(
    payload: AffiliatePostback,
    x_postback_secret: str | None = Header(default=None),
):
    from packages.shared.settings_store import get_runtime

    expected = await get_runtime("affiliate_postback_secret")
    if not expected:
        expected = settings.affiliate_postback_secret
    if x_postback_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid postback secret")

    lead = None
    if payload.lead_id:
        lead = await get_lead_by_id(payload.lead_id)
    elif payload.email:
        lead = await get_lead_by_email(payload.email)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    status_map = {"trial_start": "trial_started", "signup": "converted"}
    new_status = status_map.get(payload.event_type)

    async with get_connection() as conn:
        product_slug = await get_runtime("affiliate_product_slug") or settings.affiliate_product_slug
        product = await conn.fetchrow(
            "SELECT id FROM affiliate_products WHERE slug = $1", product_slug,
        )
        await conn.execute(
            """INSERT INTO conversions (lead_id, product_id, affiliate_tx_id, event_type, commission_amount)
               VALUES ($1, $2, $3, $4, $5)""",
            lead["id"], product["id"], payload.affiliate_tx_id,
            payload.event_type, payload.commission_amount,
        )
        if new_status:
            await conn.execute(
                "UPDATE leads SET status = $2::lead_status WHERE id = $1",
                lead["id"], new_status,
            )

    xp_event = "trial_started" if payload.event_type == "trial_start" else "conversion"
    if payload.event_type in ("trial_start", "signup"):
        gamification = await award_xp(xp_event, f"{payload.event_type}: {lead['email']}")
    else:
        gamification = {}

    return {"ok": True, "lead_id": str(lead["id"]), "gamification": gamification}


@app.post("/ops/daily-report")
async def daily_report():
    metrics = await app.state.ops.collect_daily_metrics()
    report = await app.state.ops.generate_report()
    return {"metrics": metrics, "report": report}
