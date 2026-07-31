-- Amplivo Clips – marketplace clipper tables

CREATE TABLE IF NOT EXISTS clip_campaigns (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  marketplace     TEXT NOT NULL DEFAULT 'manual',
  external_id     TEXT,
  title           TEXT NOT NULL,
  source_url      TEXT NOT NULL,
  brief           TEXT,
  payout_model    TEXT NOT NULL DEFAULT 'cpm',
  payout_rate     NUMERIC(10,4),
  currency        TEXT NOT NULL DEFAULT 'USD',
  status          TEXT NOT NULL DEFAULT 'open',
  metadata        JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (marketplace, external_id)
);

CREATE TABLE IF NOT EXISTS clip_jobs (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id     UUID NOT NULL REFERENCES clip_campaigns(id) ON DELETE CASCADE,
  status          TEXT NOT NULL DEFAULT 'queued',
  -- queued | producing | qa | ready | posted | submitted | paid | failed | rejected
  opus_project_id TEXT,
  clip_url        TEXT,
  post_url        TEXT,
  proof_url       TEXT,
  qa_score        INT,
  qa_notes        TEXT,
  error_message   TEXT,
  payout_amount   NUMERIC(10,2),
  metadata        JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clip_jobs_status ON clip_jobs(status);
CREATE INDEX IF NOT EXISTS idx_clip_campaigns_status ON clip_campaigns(status);
