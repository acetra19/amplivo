-- Systeme.io / solopreneur email sequence templates (safe to re-run)

UPDATE email_sequence_steps AS s
SET
  subject_tpl = v.subject_tpl,
  body_tpl = v.body_tpl
FROM email_sequences AS es,
LATERAL (VALUES
  (1, 'Quick question about {{company}}''s online setup',
   E'Hi {{first_name}},\n\nI noticed {{company}} is active in {{industry}}. Many coaches and online entrepreneurs still pay for 3–5 separate tools (funnels, email, courses, payments).\n\nWe help founders consolidate that stack with an all-in-one platform — most start on a free plan with no credit card.\n\nWould it help if I sent you a free account link?\n\nBest,\n{{sender_name}}'),
  (2, 'Re: Quick question about {{company}}',
   E'Hi {{first_name}},\n\nJust following up — happy to share how similar online businesses cut tool costs and launch faster with one dashboard for funnels, email, and sales.\n\nReply "interested" and I will send the free signup link.\n\nBest,\n{{sender_name}}'),
  (3, 'Last note – {{company}}',
   E'Hi {{first_name}},\n\nLast email from me. If simplifying your online business stack is not a priority right now, no worries.\n\nIf it is, reply "interested" and I will send free access.\n\nBest,\n{{sender_name}}')
) AS v(step_order, subject_tpl, body_tpl)
WHERE s.sequence_id = es.id
  AND es.slug = 'outbound_a'
  AND s.step_order = v.step_order;

UPDATE email_sequence_steps AS s
SET
  subject_tpl = v.subject_tpl,
  body_tpl = v.body_tpl
FROM email_sequences AS es,
LATERAL (VALUES
  (1, 'Free guide: launching {{industry}} online',
   E'Hi {{first_name}},\n\nI put together a short guide on how businesses like {{company}} launch funnels and email automation without a big tech stack.\n\nNo pitch — just practical steps. Want me to send it over?\n\nBest,\n{{sender_name}}'),
  (2, 'Re: online launch guide',
   E'Hi {{first_name}},\n\nJust checking in — happy to share the guide if useful.\n\nMany solopreneurs use an all-in-one platform to replace multiple subscriptions. I can point you to a free plan if you want to explore.\n\nBest,\n{{sender_name}}')
) AS v(step_order, subject_tpl, body_tpl)
WHERE s.sequence_id = es.id
  AND es.slug = 'nurture_b'
  AND s.step_order = v.step_order;
