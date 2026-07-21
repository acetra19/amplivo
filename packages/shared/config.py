"""Shared configuration for all agents."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://agentur:agentur_dev@localhost:5432/agentur"
    redis_url: str = "redis://localhost:6379/0"

    # LLM provider: "groq" (cheaper/free) or "anthropic"
    llm_provider: str = "groq"

    groq_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Groq defaults (free tier friendly)
    default_llm_model: str = "llama-3.3-70b-versatile"
    classifier_model: str = "llama-3.1-8b-instant"
    premium_llm_model: str = "llama-3.3-70b-versatile"

    # Anthropic alternatives (set LLM_PROVIDER=anthropic)
    # default_llm_model: claude-3-5-haiku-20241022
    # classifier_model: claude-3-5-haiku-20241022
    # premium_llm_model: claude-sonnet-4-20250514

    # Email – Brevo (free tier: 300/day) replaces Instantly in lean phase
    brevo_api_key: str = ""
    resend_api_key: str = ""
    outbound_from_email: str = "james@amplivo.net"
    outbound_from_name: str = "Amplivo Sales Team"
    outbound_reply_to_email: str = "reply@reply.amplivo.net"
    daily_email_limit: int = 30

    # Optional – only needed when scaling past ~100 emails/day
    instantly_api_key: str = ""

    attio_api_key: str = ""
    clay_api_key: str = ""
    apollo_api_key: str = ""

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    deepgram_api_key: str = ""
    elevenlabs_api_key: str = ""

    affiliate_product_slug: str = "systeme-io"
    affiliate_tracking_base: str = "https://systeme.io/de?sa=sa0276553274cd169665f8769608156721f068edf7"
    affiliate_postback_secret: str = ""

    landing_domain: str = ""
    cors_origins: str = "*"

    icp_industry: str = "online_business"
    icp_min_employees: int = 1
    icp_max_employees: int = 20
    lead_score_threshold: int = 70

    n8n_webhook_base: str = "http://localhost:5678"
    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
