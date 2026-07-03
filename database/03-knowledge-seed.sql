-- GoHighLevel product knowledge for RAG / chat qualifier
-- Loaded automatically on first Postgres init

INSERT INTO knowledge_chunks (product_id, source, title, content)
SELECT p.id, src.source, src.title, src.content
FROM affiliate_products p
CROSS JOIN (VALUES
  ('faq', 'What is GoHighLevel?',
   'GoHighLevel is an all-in-one platform for marketing agencies. It combines CRM, funnels, websites, email/SMS automation, calendars, and reputation management. Agencies use it to manage clients and white-label the platform under their own brand.'),

  ('faq', 'Who is GoHighLevel for?',
   'GoHighLevel is built for marketing agencies, SMMA owners, freelancers, and consultants who manage multiple clients. Typical users have 2–50 employees and need a unified system instead of juggling 5–10 separate tools.'),

  ('faq', 'Free trial details',
   'GoHighLevel offers a 14-day free trial on paid plans. Users can explore CRM, funnel builder, automation workflows, and client sub-accounts. No long-term contract required to start the trial.'),

  ('faq', 'Pricing overview',
   'Plans typically start around $97/month for the Starter plan and go up to $497/month for the Agency Pro plan with full white-label features. Annual billing often provides a discount. Pricing may change – confirm on the official site.'),

  ('faq', 'White-label capabilities',
   'Agency plans allow white-labeling: custom domain, branded mobile app, and client sub-accounts. Agencies can resell the platform to local businesses under their own brand.'),

  ('faq', 'CRM and pipeline features',
   'The CRM includes contact management, opportunity pipelines, task automation, and appointment scheduling. Agencies can track every lead from first touch to close and automate follow-up sequences.'),

  ('faq', 'Automation and workflows',
   'Users can build multi-step automations triggered by form submissions, tag changes, appointment bookings, or pipeline stage moves. Supports email, SMS, and internal notifications.'),

  ('faq', 'Common objections – already using HubSpot',
   'HubSpot is strong for enterprise sales teams but expensive at scale. GoHighLevel is agency-focused with white-label, sub-accounts, and funnel tools included – often at a lower total cost for agencies managing multiple clients.'),

  ('faq', 'Common objections – too complex',
   'There is a learning curve, but the platform includes templates, snapshots, and a large community. Most agencies are operational within the first week of the trial with guided setup.'),

  ('case_study', 'Typical agency results',
   'Agencies report consolidating 5+ tools into one platform, reducing software spend and improving client follow-up speed. Common wins: automated appointment reminders, pipeline visibility, and faster onboarding of new clients.')

) AS src(source, title, content)
WHERE p.slug = 'gohighlevel'
  AND NOT EXISTS (SELECT 1 FROM knowledge_chunks k WHERE k.product_id = p.id LIMIT 1);

CREATE INDEX IF NOT EXISTS idx_knowledge_fts ON knowledge_chunks
  USING gin(to_tsvector('english', title || ' ' || content));
