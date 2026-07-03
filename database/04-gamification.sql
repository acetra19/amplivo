-- Gamification schema: XP, levels, achievements, daily quests

CREATE TABLE IF NOT EXISTS operator_profile (
  id            INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  display_name  TEXT NOT NULL DEFAULT 'Agent Commander',
  xp_total      INT NOT NULL DEFAULT 0,
  streak_days   INT NOT NULL DEFAULT 0,
  last_active   DATE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO operator_profile (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS achievement_defs (
  slug          TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  description   TEXT NOT NULL,
  icon          TEXT NOT NULL DEFAULT '🏆',
  xp_reward     INT NOT NULL DEFAULT 0,
  sort_order    INT NOT NULL DEFAULT 0
);

INSERT INTO achievement_defs (slug, title, description, icon, xp_reward, sort_order) VALUES
  ('first_lead',       'Scout',           'Import or capture your first lead',        '🔍',  25,  1),
  ('first_email',      'Outreach Pioneer','Send your first outbound email',           '📧',  50,  2),
  ('ten_emails',       'Email Machine',   'Send 10 outbound emails',                  '🚀', 100,  3),
  ('first_reply',      'Signal Detected', 'Receive your first email reply',           '📬',  75,  4),
  ('first_interested', 'Hot Lead',        'Classify a reply as interested',           '🔥', 150,  5),
  ('first_qualified',  'Qualifier',       'Qualify a lead via chat or scoring',       '✅', 100,  6),
  ('first_trial',      'Trial Starter',   'Record your first trial start',            '🎯', 250,  7),
  ('first_conversion', 'Money Maker',     'Land your first paid conversion',          '💰', 500,  8),
  ('level_5',          'Sales Veteran',   'Reach level 5',                            '⭐', 200,  9),
  ('streak_7',         'Consistency King','Maintain a 7-day activity streak',         '👑', 300, 10)
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS achievements_unlocked (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  achievement_slug TEXT NOT NULL REFERENCES achievement_defs(slug),
  unlocked_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(achievement_slug)
);

CREATE TABLE IF NOT EXISTS xp_events (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_type  TEXT NOT NULL,
  xp_amount   INT NOT NULL,
  description TEXT,
  metadata    JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xp_events_date ON xp_events(created_at DESC);

CREATE TABLE IF NOT EXISTS daily_quest_progress (
  quest_date    DATE NOT NULL,
  quest_slug    TEXT NOT NULL,
  current_value INT NOT NULL DEFAULT 0,
  target_value  INT NOT NULL,
  completed     BOOLEAN NOT NULL DEFAULT false,
  xp_reward     INT NOT NULL,
  PRIMARY KEY (quest_date, quest_slug)
);
