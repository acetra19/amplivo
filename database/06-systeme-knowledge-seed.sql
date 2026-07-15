-- Systeme.io product knowledge for RAG / chat qualifier
-- Safe to re-run (skips if chunks already exist for this product)

UPDATE affiliate_products
SET
  affiliate_url = 'https://systeme.io/de?sa=sa0276553274cd169665f8769608156721f068edf7',
  commission_pct = 60.00,
  commission_type = 'recurring',
  avg_monthly_price = 97.00,
  trial_days = 0,
  icp_notes = 'Solopreneurs, coaches, course creators, freelancers, small online businesses'
WHERE slug = 'systeme-io';

INSERT INTO knowledge_chunks (product_id, source, title, content)
SELECT p.id, src.source, src.title, src.content
FROM affiliate_products p
CROSS JOIN (VALUES
  ('faq', 'What is Systeme.io?',
   'Systeme.io is an all-in-one marketing platform for online businesses. It combines sales funnels, email marketing, websites, online courses, automation workflows, and payment processing in a single tool. Over 500,000 entrepreneurs use it to launch and grow without juggling multiple apps.'),

  ('faq', 'Who is Systeme.io for?',
   'Systeme.io is built for solopreneurs, coaches, consultants, course creators, freelancers, and small business owners who sell online. Ideal users want one affordable platform instead of paying for separate funnel, email, course, and payment tools.'),

  ('faq', 'Free plan details',
   'Systeme.io offers a forever-free plan with no credit card required. Users can build funnels, send emails, and start selling before upgrading to paid plans when they need more contacts, funnels, or advanced features.'),

  ('faq', 'Pricing overview',
   'Paid plans typically start around $17/month (Startup) and go up to $97/month (Unlimited) for full features including unlimited funnels, courses, and automation. Annual billing often provides a discount. Confirm current pricing on the official site.'),

  ('faq', 'Key features',
   'Core features include drag-and-drop funnel builder, email marketing and automation, website builder, online course hosting, membership areas, affiliate program management, appointment scheduling, and integrated payment processing with zero transaction fees on paid plans.'),

  ('faq', 'Automation and workflows',
   'Users can build multi-step automations triggered by form submissions, tag changes, purchases, or email clicks. Supports email sequences, funnel steps, and internal notifications without coding.'),

  ('faq', 'Common objections – already using ClickFunnels or Kartra',
   'Systeme.io includes courses, email, funnels, and payments in one platform at a lower price point. Many users switch to reduce monthly tool costs and simplify their stack.'),

  ('faq', 'Common objections – too basic',
   'Systeme.io covers the full launch-to-scale journey for most solopreneurs and small businesses. Templates, a template library, and an active community help users go live quickly without technical skills.'),

  ('faq', 'Common objections – switching cost',
   'Migration support and free plan access let users test before committing. Most online businesses consolidate 3–5 tools into Systeme.io and save on monthly software spend.'),

  ('case_study', 'Typical results',
   'Users report replacing multiple subscriptions (email, funnel, course, payments) with one platform, reducing costs and speeding up launch. Common wins: faster funnel setup, automated email sequences, and selling courses without a separate LMS.')

) AS src(source, title, content)
WHERE p.slug = 'systeme-io'
  AND NOT EXISTS (SELECT 1 FROM knowledge_chunks k WHERE k.product_id = p.id LIMIT 1);
