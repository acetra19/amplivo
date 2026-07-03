-- Agentic Sales Agency – Core Schema
-- Requires pgvector extension (included in pgvector/pgvector image)

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Enums ───────────────────────────────────────────────────────────────────

CREATE TYPE lead_status AS ENUM (
  'new',
  'enriched',
  'contacted',
  'replied',
  'qualified',
  'trial_started',
  'converted',
  'lost',
  'unsubscribed'
);

CREATE TYPE interaction_channel AS ENUM (
  'email',
  'chat',
  'voice',
  'sms',
  'linkedin'
);

CREATE TYPE interaction_direction AS ENUM ('inbound', 'outbound');

-- ─── Affiliate Products ──────────────────────────────────────────────────────

CREATE TABLE affiliate_products (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  slug          TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  category      TEXT NOT NULL,
  commission_pct NUMERIC(5,2),
  commission_type TEXT NOT NULL DEFAULT 'recurring', -- recurring | one_time
  cookie_days   INT NOT NULL DEFAULT 60,
  avg_monthly_price NUMERIC(10,2),
  trial_days    INT DEFAULT 14,
  affiliate_url TEXT NOT NULL,
  api_docs_url  TEXT,
  icp_notes     TEXT,
  is_active     BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Leads ───────────────────────────────────────────────────────────────────

CREATE TABLE leads (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email           TEXT UNIQUE NOT NULL,
  first_name      TEXT,
  last_name       TEXT,
  company         TEXT,
  job_title       TEXT,
  phone           TEXT,
  linkedin_url    TEXT,
  website         TEXT,
  industry        TEXT,
  employee_count  INT,
  country         TEXT DEFAULT 'DE',
  status          lead_status NOT NULL DEFAULT 'new',
  score           INT NOT NULL DEFAULT 0 CHECK (score >= 0 AND score <= 100),
  icp_match       BOOLEAN NOT NULL DEFAULT false,
  product_id      UUID REFERENCES affiliate_products(id),
  source          TEXT,           -- apollo, clay, inbound, referral
  utm_source      TEXT,
  utm_campaign    TEXT,
  metadata        JSONB NOT NULL DEFAULT '{}',
  do_not_contact  BOOLEAN NOT NULL DEFAULT false,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_score ON leads(score DESC);
CREATE INDEX idx_leads_icp ON leads(icp_match) WHERE icp_match = true;

-- ─── Interactions ────────────────────────────────────────────────────────────

CREATE TABLE interactions (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id         UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  channel         interaction_channel NOT NULL,
  direction       interaction_direction NOT NULL,
  subject         TEXT,
  body            TEXT,
  summary         TEXT,
  sentiment       TEXT,           -- positive, neutral, negative, objection
  agent_name      TEXT,
  llm_model       TEXT,
  tokens_used     INT,
  metadata        JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_interactions_lead ON interactions(lead_id, created_at DESC);

-- ─── Email Sequences ─────────────────────────────────────────────────────────

CREATE TABLE email_sequences (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  slug        TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  description TEXT,
  is_active   BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE email_sequence_steps (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  sequence_id   UUID NOT NULL REFERENCES email_sequences(id) ON DELETE CASCADE,
  step_order    INT NOT NULL,
  delay_days    INT NOT NULL DEFAULT 0,
  subject_tpl   TEXT NOT NULL,
  body_tpl      TEXT NOT NULL,
  UNIQUE(sequence_id, step_order)
);

CREATE TABLE lead_sequence_state (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id       UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  sequence_id   UUID NOT NULL REFERENCES email_sequences(id),
  current_step  INT NOT NULL DEFAULT 0,
  next_send_at  TIMESTAMPTZ,
  completed     BOOLEAN NOT NULL DEFAULT false,
  paused        BOOLEAN NOT NULL DEFAULT false,
  UNIQUE(lead_id, sequence_id)
);

-- ─── Conversions & Revenue ───────────────────────────────────────────────────

CREATE TABLE conversions (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id           UUID NOT NULL REFERENCES leads(id),
  product_id        UUID NOT NULL REFERENCES affiliate_products(id),
  affiliate_tx_id   TEXT,
  event_type        TEXT NOT NULL,  -- trial_start, signup, renewal
  commission_amount NUMERIC(10,2),
  commission_currency TEXT DEFAULT 'EUR',
  occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata          JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_conversions_lead ON conversions(lead_id);
CREATE INDEX idx_conversions_date ON conversions(occurred_at DESC);

-- ─── Knowledge Base (RAG) ────────────────────────────────────────────────────

CREATE TABLE knowledge_chunks (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  product_id  UUID REFERENCES affiliate_products(id),
  source      TEXT NOT NULL,      -- docs, faq, case_study
  title       TEXT NOT NULL,
  content     TEXT NOT NULL,
  embedding   vector(1536),
  metadata    JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_knowledge_product ON knowledge_chunks(product_id);

-- ─── Agent Runs (observability) ──────────────────────────────────────────────

CREATE TABLE agent_runs (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_name    TEXT NOT NULL,
  lead_id       UUID REFERENCES leads(id),
  input_summary TEXT,
  output_summary TEXT,
  status        TEXT NOT NULL DEFAULT 'running', -- running, success, failed
  error_message TEXT,
  duration_ms   INT,
  metadata      JSONB NOT NULL DEFAULT '{}',
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ
);

CREATE INDEX idx_agent_runs_name ON agent_runs(agent_name, started_at DESC);

-- ─── Campaign Metrics (daily rollup) ─────────────────────────────────────────

CREATE TABLE daily_metrics (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  metric_date     DATE NOT NULL,
  emails_sent     INT NOT NULL DEFAULT 0,
  emails_replied  INT NOT NULL DEFAULT 0,
  leads_qualified INT NOT NULL DEFAULT 0,
  trials_started  INT NOT NULL DEFAULT 0,
  conversions     INT NOT NULL DEFAULT 0,
  commission_total NUMERIC(10,2) NOT NULL DEFAULT 0,
  llm_cost_usd    NUMERIC(10,4) NOT NULL DEFAULT 0,
  metadata        JSONB NOT NULL DEFAULT '{}',
  UNIQUE(metric_date)
);

-- ─── Seed: default product + sequences ───────────────────────────────────────

INSERT INTO affiliate_products (slug, name, category, commission_pct, commission_type, cookie_days, avg_monthly_price, trial_days, affiliate_url, icp_notes)
VALUES
  ('gohighlevel', 'GoHighLevel', 'agency_saas', 40.00, 'recurring', 90, 297.00, 14, 'https://YOUR-AFFILIATE-LINK', 'Local marketing agencies, freelancers, SMMA'),
  ('systeme-io', 'Systeme.io', 'marketing_automation', 40.00, 'recurring', 60, 27.00, 14, 'https://YOUR-AFFILIATE-LINK', 'Solopreneurs, course creators, small agencies'),
  ('semrush', 'Semrush', 'seo_tools', 40.00, 'recurring', 120, 129.00, 7, 'https://YOUR-AFFILIATE-LINK', 'SEO agencies, content teams, in-house marketers'),
  ('hubspot', 'HubSpot', 'crm', 30.00, 'recurring', 180, 800.00, 14, 'https://YOUR-AFFILIATE-LINK', 'SMB sales teams, growing B2B companies'),
  ('clickfunnels', 'ClickFunnels', 'funnel_builder', 30.00, 'recurring', 45, 147.00, 14, 'https://YOUR-AFFILIATE-LINK', 'Coaches, info products, e-commerce funnels');

INSERT INTO email_sequences (slug, name, description) VALUES
  ('outbound_a', 'Outbound Sequence A', 'High-score ICP leads – direct value pitch'),
  ('nurture_b', 'Nurture Sequence B', 'Lower-score leads – education first');

INSERT INTO email_sequence_steps (sequence_id, step_order, delay_days, subject_tpl, body_tpl)
SELECT id, 1, 0,
  'Quick question about {{company}}''s client acquisition',
  'Hi {{first_name}},\n\nI noticed {{company}} works in {{industry}}. Many agencies your size struggle with client follow-up and pipeline visibility.\n\nWe help agencies automate outreach and close more deals with a proven platform – most teams see results within the first 14-day trial.\n\nWould a 10-minute walkthrough be useful?\n\nBest,\n{{sender_name}}'
FROM email_sequences WHERE slug = 'outbound_a';

INSERT INTO email_sequence_steps (sequence_id, step_order, delay_days, subject_tpl, body_tpl)
SELECT id, 2, 3,
  'Re: Quick question about {{company}}',
  'Hi {{first_name}},\n\nJust following up – happy to share how similar agencies cut manual follow-up by 60%.\n\nHere is a free resource: [link]\n\nOr reply with a time that works for a quick demo.\n\nBest,\n{{sender_name}}'
FROM email_sequences WHERE slug = 'outbound_a';

INSERT INTO email_sequence_steps (sequence_id, step_order, delay_days, subject_tpl, body_tpl)
SELECT id, 3, 7,
  'Last note – {{company}}',
  'Hi {{first_name}},\n\nLast email from me. If automating client acquisition is not a priority right now, no worries.\n\nIf it is, reply "interested" and I will send trial access.\n\nBest,\n{{sender_name}}'
FROM email_sequences WHERE slug = 'outbound_a';

INSERT INTO email_sequence_steps (sequence_id, step_order, delay_days, subject_tpl, body_tpl)
SELECT id, 1, 0,
  'Free guide: scaling a {{industry}} agency',
  'Hi {{first_name}},\n\nI put together a short guide on how agencies like {{company}} automate client follow-up without hiring more staff.\n\nNo pitch – just practical steps. Want me to send it over?\n\nBest,\n{{sender_name}}'
FROM email_sequences WHERE slug = 'nurture_b';

INSERT INTO email_sequence_steps (sequence_id, step_order, delay_days, subject_tpl, body_tpl)
SELECT id, 2, 5,
  'Re: agency growth guide',
  'Hi {{first_name}},\n\nJust checking in – happy to share the guide if useful.\n\nMany agencies your size use all-in-one platforms to cut tool costs. I can point you to a free trial if interested.\n\nBest,\n{{sender_name}}'
FROM email_sequences WHERE slug = 'nurture_b';

-- ─── Updated_at trigger ──────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_leads_updated BEFORE UPDATE ON leads
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_products_updated BEFORE UPDATE ON affiliate_products
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
