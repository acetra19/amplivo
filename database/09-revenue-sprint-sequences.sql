-- 7-day revenue sprint: curiosity → concrete SETUP help + affiliate soft CTA
-- Placeholders: {{first_name}} {{company}} {{industry}} {{sender_name}} {{affiliate_url}}

UPDATE email_sequence_steps AS s
SET
  subject_tpl = v.subject_tpl,
  body_tpl = v.body_tpl
FROM email_sequences AS es,
LATERAL (VALUES
  (1, 'Kurze Frage zu {{company}}',
   E'Hallo {{first_name}},\n\nkurz zu {{company}}: womit baust du aktuell Funnels, E-Mail und Kurszugang – ein Tool oder mehrere?\n\nIch frage, weil Solo-Setups dort oft unnötig Zeit verlieren. Kein Pitch, nur die eine Frage.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Kein Interesse? Antworte STOP.'),
  (2, 'Re: Kurze Frage zu {{company}}',
   E'Hallo {{first_name}},\n\nkurz nachgehakt.\n\nAngebot: Ich richte dir in 20 Minuten den kostenlosen Systeme.io-Account + einen ersten Funnel ein (ohne Kreditkarte).\n\n1) Free-Zugang hier anlegen:\n{{affiliate_url}}\n2) Antworte mit SETUP – dann machen wir den Rest gemeinsam per Mail.\n\nWenn es nicht passt: ignorieren oder STOP.\n\nBeste Gruesse\n{{sender_name}}'),
  (3, 'Letzte Nachricht – Setup-Hilfe {{company}}',
   E'Hallo {{first_name}},\n\nletzte Mail von mir.\n\nFalls Stack gerade Thema ist: Free-Account + 20-Min Setup-Hilfe von mir.\nZugang:\n{{affiliate_url}}\n\nAntworte SETUP wenn du willst – sonst alles gut.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. STOP zum Abmelden.')
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
  (1, 'Kurze Frage an {{company}}',
   E'Hallo {{first_name}},\n\nbei {{company}}: laeuft Funnel + E-Mail + Kurs schon in einem System – oder noch getrennt?\n\nNur diese eine Frage.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Antworte STOP zum Abmelden.'),
  (2, 'Re: Tool-Setup {{company}}',
   E'Hallo {{first_name}},\n\nkurz der Reminder.\n\nWenn getrennte Tools nerven: Free-Plan Systeme.io + ich helfe 20 Min beim ersten Funnel.\n{{affiliate_url}}\n\nAntworte SETUP – sonst einfach ignorieren.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. STOP zum Abmelden.')
) AS v(step_order, subject_tpl, body_tpl)
WHERE s.sequence_id = es.id
  AND es.slug = 'nurture_b'
  AND s.step_order = v.step_order;
