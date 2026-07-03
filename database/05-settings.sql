-- Runtime app settings (editable via dashboard GUI)

CREATE TABLE IF NOT EXISTS app_settings (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL DEFAULT '',
  is_secret   BOOLEAN NOT NULL DEFAULT false,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed empty rows so the GUI always has fields to bind
INSERT INTO app_settings (key, is_secret) VALUES
  ('llm_provider', false),
  ('groq_api_key', true),
  ('anthropic_api_key', true),
  ('default_llm_model', false),
  ('classifier_model', false),
  ('brevo_api_key', true),
  ('outbound_from_email', false),
  ('outbound_from_name', false),
  ('daily_email_limit', false),
  ('api_domain', false),
  ('landing_domain', false),
  ('dashboard_domain', false),
  ('n8n_host', false),
  ('n8n_webhook_url', false),
  ('affiliate_product_slug', false),
  ('affiliate_tracking_base', false),
  ('affiliate_postback_secret', true),
  ('icp_industry', false),
  ('icp_min_employees', false),
  ('icp_max_employees', false),
  ('lead_score_threshold', false),
  ('settings_pin', true)
ON CONFLICT (key) DO NOTHING;
